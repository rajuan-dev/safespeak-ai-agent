import base64
import re
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.modules.auth.dependencies import Principal
from app.services.llm import llm_service

from .context_builder import build_safe_speak_context
from .guardrails import (
    build_compact_retry_instruction,
    build_guardrail_revision_instruction,
    build_guardrails,
    enforce_ai_output_guardrails,
    normalize_triage_output,
    validate_safe_speak_response,
)
from .intent_classifier import classify_safe_speak_intent_details
from .model import AI_ACTIONS, AI_REVIEW_STATUSES
from .prompts import (
    build_clarifying_prompt,
    build_conversation_prompt,
    build_extract_prompt,
    build_summary_prompt,
    build_translate_prompt,
    build_triage_prompt,
)
from .repository import AiRepository, get_ai_repository
from .schema import (
    ClarifyingQuestionsInput,
    ExtractIncidentFieldsInput,
    GenerateSummaryInput,
    RedactInput,
    SynthesizeSpeechInput,
    TranscribeAudioInput,
    TranslateInput,
    TriageInput,
)

SUPPORTED_TRANSCRIPTION_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/webm",
    "audio/mp4",
    "audio/m4a",
    "video/mp4",
    "video/webm",
}
MAX_SPEECH_TEXT_LENGTH = 4000


class JsonCompletionPort(Protocol):
    async def json_completion(
        self,
        *,
        system: str,
        user: str,
        fallback: dict[str, Any],
        temperature: float = 0.2,
        model: str | None = None,
    ) -> dict[str, Any]: ...


def _normalize_speech_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:MAX_SPEECH_TEXT_LENGTH]


def _default_conversation_reply(
    *,
    session: dict[str, Any],
    latest_user_message: str,
    language: str,
) -> dict[str, Any]:
    lower = latest_user_message.lower()
    if any(token in lower for token in ("unsafe", "danger", "threat", "emergency")):
        body = "I’m here with you. If there is immediate danger, focus on your safety first."
        question = "Are you safe right now, or is there an urgent risk around you?"
        risk = "high"
    elif any(token in lower for token in ("scam", "fraud", "bank", "otp")):
        body = (
            "What you described sounds serious, and we can keep this to the "
            "smallest useful next step."
        )
        question = "Did they take money already, or do they mainly have your details right now?"
        risk = "medium"
    else:
        body = (
            "You do not need to explain everything at once, and we can take this "
            "one step at a time."
        )
        question = "What feels most important for me to understand first about what happened?"
        risk = session.get("latestTurnRiskLevel") or "low"
    return {
        "assistantMessage": body,
        "nextQuestion": question,
        "confidence": "medium",
        "disclaimer": "This is information only, not legal advice.",
        "intent": "conversation_support",
        "responseMode": "support_victim_style",
        "selectedResponseSource": "conversation_flow_rule_based",
        "responseSource": "conversation_flow_rule_based",
        "reviewStatus": AI_REVIEW_STATUSES["conversationSupport"],
        "assistantLanguage": language,
        "triageUpdated": True,
        "latestTurnRiskLevel": risk,
        "activeIncidentRiskLevel": risk,
        "sessionHistoricalMaxRiskLevel": risk,
        "showSources": False,
        "rag": {"used": False, "unavailable": False, "resultCount": 0},
    }


def _interaction_envelope(
    output: dict[str, Any],
    *,
    citations: list[dict[str, Any]],
    language: str | None = None,
) -> dict[str, Any]:
    return {
        "interactionId": str(uuid4()),
        "output": output,
        "citations": citations,
        "guardrails": build_guardrails(
            language or output.get("language") or output.get("targetLanguage")
        ),
        "reviewStatus": AI_REVIEW_STATUSES["pendingHumanReview"],
    }


async def _record_interaction(
    *,
    repository: AiRepository,
    principal: Principal | None,
    action: str,
    request_payload: dict[str, Any],
    output_payload: dict[str, Any],
    language: str | None,
    report_id: str | None = None,
    error: str | None = None,
) -> None:
    if principal is None:
        return
    settings = get_settings()
    try:
        await repository.create_ai_interaction(
            principal=principal,
            action=action,
            model=settings.OPENAI_MODEL,
            language=language,
            request_payload=request_payload,
            output_payload=output_payload,
            guardrails=build_guardrails(language),
            review_status=output_payload.get(
                "reviewStatus", AI_REVIEW_STATUSES["pendingHumanReview"]
            ),
            citations=output_payload.get("citations") or [],
            report_id=report_id,
            error=error,
        )
    except Exception:
        return


async def _build_report_context(
    principal: Principal | None,
    report_id: str | None,
    *,
    repository: AiRepository,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not report_id:
        return None, []
    if principal is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")
    report = await repository.find_owned_report(principal, report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    citations = []
    excerpt = report.get("originalNarrative") or report.get("context")
    citations.append(
        {
            "sourceType": "report",
            "sourceId": str(report["_id"]),
            "title": report.get("refNo"),
            "excerpt": excerpt[:400] if isinstance(excerpt, str) else None,
        }
    )
    evidence = await repository.list_report_evidence(principal, report["_id"])
    citations.extend(
        [
            {
                "sourceType": "evidence",
                "sourceId": str(item["_id"]),
                "title": item.get("fileName"),
                "excerpt": (
                    f"Evidence metadata: {item.get('mimeType')}, status {item.get('status')}, "
                    f"sha256 {item.get('sha256Hash') or 'not available'}"
                ),
            }
            for item in evidence
        ]
    )
    return report, citations


async def extract_incident_fields(
    request: ExtractIncidentFieldsInput,
    principal: Principal | None = None,
    *,
    repository: AiRepository | None = None,
    llm: JsonCompletionPort | None = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    llm = llm or llm_service
    _report, citations = await _build_report_context(
        principal,
        request.reportId,
        repository=repository,
    )
    output = await llm.json_completion(
        system=build_extract_prompt(),
        user=request.narrative,
        fallback={
            "incidentType": request.incidentCategory,
            "what": request.narrative,
            "missingInformation": ["Model unavailable; review the narrative manually."],
            "reviewStatus": AI_REVIEW_STATUSES["pendingHumanReview"],
        },
    )
    result = _interaction_envelope(output, citations=citations, language=request.language)
    await _record_interaction(
        repository=repository,
        principal=principal,
        action=AI_ACTIONS["extractIncidentFields"],
        request_payload=request.model_dump(by_alias=True, exclude_none=True),
        output_payload=result,
        language=request.language,
        report_id=request.reportId,
    )
    return result


async def clarifying_questions(
    request: ClarifyingQuestionsInput,
    principal: Principal | None = None,
    *,
    repository: AiRepository | None = None,
    llm: JsonCompletionPort | None = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    llm = llm or llm_service
    _report, citations = await _build_report_context(
        principal,
        request.reportId,
        repository=repository,
    )
    output = await llm.json_completion(
        system=build_clarifying_prompt(request.maxQuestions),
        user=f"Narrative: {request.narrative}\nKnown fields: {request.structuredFields or {}}",
        fallback={
            "questions": ["When did this happen?", "Where did it happen?"][: request.maxQuestions],
            "rationale": "Basic timeline details are missing.",
            "reviewStatus": AI_REVIEW_STATUSES["pendingHumanReview"],
        },
    )
    result = _interaction_envelope(output, citations=citations, language=request.language)
    await _record_interaction(
        repository=repository,
        principal=principal,
        action=AI_ACTIONS["clarifyingQuestions"],
        request_payload=request.model_dump(by_alias=True, exclude_none=True),
        output_payload=result,
        language=request.language,
        report_id=request.reportId,
    )
    return result


async def generate_summary(
    request: GenerateSummaryInput,
    principal: Principal | None = None,
    *,
    repository: AiRepository | None = None,
    llm: JsonCompletionPort | None = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    llm = llm or llm_service
    report, citations = await _build_report_context(
        principal,
        request.reportId,
        repository=repository,
    )
    narrative = request.narrative
    if report and not narrative:
        narrative = report.get("originalNarrative") or report.get("translatedNarrative") or ""
    structured_fields = request.structuredFields or (
        report.get("structuredFields") if report else {}
    )
    output = await llm.json_completion(
        system=build_summary_prompt(),
        user=(
            f"Create an information-only summary for audience {request.audience}. "
            f"Narrative: {narrative or ''}\nFields: {structured_fields or {}}"
        ),
        fallback={
            "summary": narrative or "",
            "keyFacts": [],
            "uncertaintyNotes": ["Automated summarisation was unavailable."],
            "reviewStatus": AI_REVIEW_STATUSES["pendingHumanReview"],
        },
    )
    result = _interaction_envelope(output, citations=citations, language=request.language)
    await _record_interaction(
        repository=repository,
        principal=principal,
        action=AI_ACTIONS["generateSummary"],
        request_payload=request.model_dump(by_alias=True, exclude_none=True),
        output_payload=result,
        language=request.language,
        report_id=request.reportId,
    )
    return result


async def triage_report(
    request: TriageInput,
    principal: Principal | None = None,
    *,
    repository: AiRepository | None = None,
    llm: JsonCompletionPort | None = None,
    platform_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    llm = llm or llm_service
    report, citations = await _build_report_context(
        principal,
        request.reportId,
        repository=repository,
    )
    platform_settings = platform_settings or await repository.get_public_platform_settings()
    ai_settings = platform_settings["ai"]
    language = request.language or (report.get("language") if report else None)
    narrative = request.narrative or ""
    if report and not narrative:
        narrative = report.get("originalNarrative") or report.get("translatedNarrative") or ""
    structured_fields = request.structuredFields or (
        report.get("structuredFields") if report else None
    )
    output = await llm.json_completion(
        system=build_triage_prompt(ai_settings),
        user=(
            f"Narrative: {narrative}\n"
            f"Structured fields: {structured_fields or {}}\n"
            + (
                f"The report came from the quick-start category: {request.incidentCategory}. "
                "Use it to tailor support and resources, but do not invent facts not grounded "
                "in the narrative or structured fields."
                if request.incidentCategory
                else "No quick-start category was provided."
            )
        ),
        fallback={
            "severitySignal": "unknown",
            "primarySupportNeed": "human_review",
            "summary": narrative,
            "assessmentBody": "Automated triage was unavailable.",
            "riskFactors": [],
            "suggestedSupportCategories": [],
            "recommendedActions": ["Review this report with a qualified support worker."],
            "resourceRecommendations": [],
            "nonLegalSafetyNotes": [],
            "immediateSafetyFlag": False,
            "confidence": "low",
            "pendingHumanReview": True,
            "reviewStatus": AI_REVIEW_STATUSES["pendingHumanReview"],
        },
    )
    normalized = normalize_triage_output(
        model_output=output,
        narrative=narrative,
        structured_fields=structured_fields,
        citations=citations,
        disclaimer=ai_settings["disclaimerText"],
        human_review_note=ai_settings["humanReviewText"],
        fallback_text=ai_settings["triageFallbackText"],
    )
    normalized["guardrails"] = build_guardrails(language)
    normalized["interactionId"] = str(uuid4())
    normalized["model"] = get_settings().OPENAI_MODEL
    normalized["templateVersion"] = platform_settings["version"]
    normalized["templateStatus"] = ai_settings["triageTemplateStatus"]
    await _record_interaction(
        repository=repository,
        principal=principal,
        action=AI_ACTIONS["triageReport"],
        request_payload=request.model_dump(by_alias=True, exclude_none=True),
        output_payload=normalized,
        language=language,
        report_id=request.reportId,
    )
    return normalized


async def translate(
    request: TranslateInput,
    principal: Principal | None = None,
    *,
    repository: AiRepository | None = None,
    llm: JsonCompletionPort | None = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    llm = llm or llm_service
    output = await llm.json_completion(
        system=build_translate_prompt(),
        user=(
            f"Source language: {request.sourceLanguage or 'auto-detect'}\n"
            f"Target language: {request.targetLanguage}\nText: {request.text}"
        ),
        fallback={
            "translatedText": request.text,
            "sourceLanguage": request.sourceLanguage,
            "targetLanguage": request.targetLanguage,
            "reviewStatus": AI_REVIEW_STATUSES["pendingHumanReview"],
        },
    )
    result = _interaction_envelope(
        output,
        citations=[{"sourceType": "user_input", "excerpt": request.text[:400]}],
        language=request.targetLanguage,
    )
    await _record_interaction(
        repository=repository,
        principal=principal,
        action=AI_ACTIONS["translate"],
        request_payload=request.model_dump(by_alias=True, exclude_none=True),
        output_payload=result,
        language=request.targetLanguage,
    )
    return result


def redact_pii(
    request: RedactInput,
    principal: Principal | None = None,
    *,
    repository: AiRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    patterns = [
        ("EMAIL", r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        ("PHONE", r"(?<!\d)(?:\+?61|0)[2-478](?:[ -]?\d){8}(?!\d)"),
        ("CARD", r"\b(?:\d[ -]*?){13,19}\b"),
    ]
    redacted = request.text
    entities: list[dict[str, Any]] = []
    for label, pattern in patterns:
        matches = list(re.finditer(pattern, redacted, flags=re.IGNORECASE))
        for match in reversed(matches):
            replacement = (
                f"[{label}]" if request.replacementStyle == "labels" else "*" * len(match.group())
            )
            entities.append({"type": label, "start": match.start(), "end": match.end()})
            redacted = redacted[: match.start()] + replacement + redacted[match.end() :]
    result = _interaction_envelope(
        {
            "redactedText": redacted,
            "detectedEntities": list(reversed(entities)),
            "replacementStyle": request.replacementStyle,
            "reviewStatus": AI_REVIEW_STATUSES["automatedReviewRequired"],
        },
        citations=[{"sourceType": "user_input", "excerpt": request.text[:400]}],
        language=request.language,
    )
    return result


async def transcribe_audio_file(
    request: TranscribeAudioInput,
    *,
    principal: Principal | None,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    repository: AiRepository | None = None,
    http_client_factory: Any = None,
    settings_factory: Any = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    settings_factory = settings_factory or get_settings
    settings = settings_factory()
    if principal is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")
    if not file_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "audio file is required")
    if mime_type not in SUPPORTED_TRANSCRIPTION_MIME_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Unsupported audio/video file type for transcription",
        )
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OPENAI_API_KEY is not configured")
    client_factory = http_client_factory or (lambda timeout: httpx.AsyncClient(timeout=timeout))
    files = {"file": (file_name or "audio-input.webm", file_bytes, mime_type)}
    data = {"model": settings.OPENAI_TRANSCRIPTION_MODEL}
    if request.language:
        data["language"] = request.language
    async with client_factory(120.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            data=data,
            files=files,
        )
    if response.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAI transcription request failed")
    payload = response.json()
    transcript = payload.get("text")
    if not isinstance(transcript, str) or not transcript.strip():
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAI transcription response was empty")
    saved = request.saveTranscript is not False
    if request.evidenceId and saved:
        evidence = await repository.find_owned_evidence(principal, request.evidenceId)
        if not evidence:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
        await repository.update_evidence_transcription(
            evidence["_id"],
            {
                "text": transcript,
                "language": payload.get("language"),
                "model": settings.OPENAI_TRANSCRIPTION_MODEL,
                "provider": "openai",
                "transcribedAt": datetime.now(UTC),
                "transcribedBy": principal.user_id or principal.session_id,
            },
        )
    if request.reportId:
        report = await repository.find_owned_report(principal, request.reportId)
        if not report:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
        if request.useAsNarrative:
            consent_snapshot = report.get("consentSnapshot") or {}
            if not consent_snapshot.get("cloud_sync"):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "cloud_sync consent is required to store transcription as report narrative",
                )
            await repository.update_report_narrative(report["_id"], transcript)
        else:
            structured_fields = report.get("structuredFields") or {}
            structured_fields["transcription"] = {
                "available": True,
                "language": payload.get("language"),
                "model": settings.OPENAI_TRANSCRIPTION_MODEL,
            }
            await repository.update_report_structured_fields(report["_id"], structured_fields)
    result = {
        "transcript": transcript,
        "language": payload.get("language"),
        "model": settings.OPENAI_TRANSCRIPTION_MODEL,
        "reportId": request.reportId,
        "evidenceId": request.evidenceId,
        "saved": saved,
    }
    await _record_interaction(
        repository=repository,
        principal=principal,
        action=AI_ACTIONS["transcribeAudio"],
        request_payload=request.model_dump(by_alias=True, exclude_none=True),
        output_payload=result,
        language=request.language or payload.get("language"),
        report_id=request.reportId,
    )
    return result


async def synthesize_speech(
    request: SynthesizeSpeechInput,
    principal: Principal | None = None,
    *,
    repository: AiRepository | None = None,
    http_client_factory: Any = None,
    settings_factory: Any = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    settings_factory = settings_factory or get_settings
    settings = settings_factory()
    text = _normalize_speech_text(request.text)
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "text is required")
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OPENAI_API_KEY is not configured")
    voice = request.voice or settings.OPENAI_TTS_VOICE
    client_factory = http_client_factory or (lambda timeout: httpx.AsyncClient(timeout=timeout))
    async with client_factory(120.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.OPENAI_TTS_MODEL,
                "voice": voice,
                "input": text,
                "response_format": "mp3",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAI speech synthesis request failed")
    result = {
        "audioBase64": base64.b64encode(response.content).decode("ascii"),
        "mimeType": "audio/mpeg",
        "model": settings.OPENAI_TTS_MODEL,
        "voice": voice,
        "temporary": True,
    }
    await _record_interaction(
        repository=repository,
        principal=principal,
        action=AI_ACTIONS["synthesizeSpeech"],
        request_payload=request.model_dump(by_alias=True, exclude_none=True),
        output_payload=result,
        language=request.language,
    )
    return result


async def generate_conversation_response(
    *,
    session: dict[str, Any],
    messages: list[dict[str, Any]],
    latest_user_message: str,
    language: str,
    consent: dict[str, bool],
    repository: AiRepository | None = None,
    llm: JsonCompletionPort | None = None,
) -> dict[str, Any]:
    repository = repository or get_ai_repository()
    if not consent.get("process_with_ai"):
        return _default_conversation_reply(
            session=session,
            latest_user_message=latest_user_message,
            language=language,
        )
    llm = llm or llm_service
    classification = classify_safe_speak_intent_details(latest_user_message)
    facts = {"timeline": session.get("timeline") or {}}
    context = build_safe_speak_context(
        session=session,
        messages=messages,
        facts=facts,
        classification=classification,
        consent=consent,
    )
    fallback = _default_conversation_reply(
        session=session,
        latest_user_message=latest_user_message,
        language=language,
    )
    output = await llm.json_completion(
        system=build_conversation_prompt(context),
        user=(
            f"Latest user message: {latest_user_message}\n"
            f"Context: {context}\n"
            f"Retry rule: {build_compact_retry_instruction()}\n"
            f"Guardrail rule: {build_guardrail_revision_instruction()}"
        ),
        fallback=fallback,
    )
    response_text = " ".join(
        part
        for part in (
            str(output.get("assistantMessage") or "").strip(),
            str(output.get("nextQuestion") or "").strip(),
        )
        if part
    )
    safety = validate_safe_speak_response(response_text)
    if safety["requiresHumanReview"]:
        output.setdefault("reviewStatus", AI_REVIEW_STATUSES["pendingHumanReview"])
    output["assistantMessage"] = enforce_ai_output_guardrails(
        str(output.get("assistantMessage") or fallback["assistantMessage"])
    )
    output["nextQuestion"] = enforce_ai_output_guardrails(
        str(output.get("nextQuestion") or fallback["nextQuestion"])
    )
    output.setdefault("confidence", fallback["confidence"])
    output.setdefault("intent", classification["intent"])
    output.setdefault("responseMode", "support_victim_style")
    output.setdefault("selectedResponseSource", "conversation_flow_ai")
    output.setdefault("responseSource", "conversation_flow_ai")
    output.setdefault("reviewStatus", AI_REVIEW_STATUSES["conversationSupport"])
    output.setdefault("assistantLanguage", language)
    output.setdefault("triageUpdated", True)
    output.setdefault(
        "latestTurnRiskLevel",
        "high" if safety["crisisRisk"] else session.get("latestTurnRiskLevel") or "medium",
    )
    output.setdefault("activeIncidentRiskLevel", output["latestTurnRiskLevel"])
    output.setdefault("sessionHistoricalMaxRiskLevel", output["latestTurnRiskLevel"])
    output.setdefault("showSources", False)
    output.setdefault("rag", {"used": False, "unavailable": False, "resultCount": 0})
    output["disclaimer"] = "This is information only, not legal advice."
    await _record_interaction(
        repository=repository,
        principal=None,
        action=AI_ACTIONS["conversationResponse"],
        request_payload={
            "language": language,
            "message": latest_user_message,
            "messageCount": len(messages),
            "consent": {"process_with_ai": bool(consent.get("process_with_ai"))},
        },
        output_payload=output,
        language=language,
    )
    return output


class SafeSpeakConversationAssistant:
    async def respond(
        self,
        *,
        session: dict[str, Any],
        messages: list[dict[str, Any]],
        latest_user_message: str,
        language: str,
        consent: dict[str, bool],
    ) -> dict[str, Any]:
        return await generate_conversation_response(
            session=session,
            messages=messages,
            latest_user_message=latest_user_message,
            language=language,
            consent=consent,
            repository=get_ai_repository(),
        )


def get_conversation_assistant() -> SafeSpeakConversationAssistant:
    return SafeSpeakConversationAssistant()
