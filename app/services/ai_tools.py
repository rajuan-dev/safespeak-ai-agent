import base64
from copy import deepcopy
import re
from typing import Any
from uuid import uuid4

import httpx
from bson import ObjectId
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.database import get_database
from app.core.security import Principal
from app.models.ai import (
    RedactInput,
    ClarifyingQuestionsInput,
    ExtractIncidentFieldsInput,
    GenerateSummaryInput,
    SynthesizeSpeechInput,
    TranscribeAudioInput,
    TranslateInput,
    TriageInput,
)
from app.services.llm import llm_service

INFORMATION_ONLY_DISCLAIMER = (
    "This is general information only, not legal advice. For personal legal help, "
    "contact a qualified lawyer, Legal Aid, or a relevant support service."
)
LEGAL_ADVICE_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsuing is an option\b",
        r"\byou can sue\b",
        r"\byou should sue\b",
        r"\byou must sue\b",
        r"\byou have a case\b",
        r"\bthis is definitely illegal\b",
        r"\bthat is definitely illegal\b",
        r"\bthey broke the law\b",
        r"\byou will win\b",
        r"\byou are entitled to compensation\b",
    )
]
CLINICAL_ADVICE_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\byou have (ptsd|depression|anxiety|trauma)\b",
        r"\bi diagnose\b",
        r"\bclinical advice\b",
        r"\bmedical advice\b",
        r"\btake (this )?medication\b",
        r"\bstop taking (your )?medication\b",
        r"\btherapy plan\b",
    )
]
CRISIS_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi am in danger\b",
        r"\bi'?m in danger\b",
        r"\bimmediate danger\b",
        r"\bi am unsafe\b",
        r"\bi'?m unsafe\b",
        r"\bunsafe right now\b",
        r"\bi need help now\b",
        r"\bpartner is threatening me\b",
        r"\bmy partner is threatening me\b",
        r"\bdomestic violence\b",
        r"\bthreat to life\b",
        r"\bviolence now\b",
    )
]
TRIAGE_SEVERITY_VALUES = {"low", "medium", "high", "urgent"}
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
DEFAULT_PLATFORM_SETTINGS = {
    "ai": {
        "disclaimerText": (
            "This output is information-only and must not be treated as legal, medical, "
            "counselling, crisis, or case-management advice."
        ),
        "humanReviewText": (
            "AI-generated content may require human review before use in formal reports."
        ),
        "triageSystemPrompt": (
            "Triage reports into information-only support guidance. Do not give legal, "
            "clinical, crisis-service, counselling, or case-management advice. Use general "
            "options language and flag uncertain or high-risk content for human review."
        ),
        "triageResponseTemplate": (
            "Return severitySignal, primarySupportNeed, specialtyTag, summary, assessmentBody, "
            "riskFactors, suggestedSupportCategories, recommendedActions, "
            "resourceRecommendations, nonLegalSafetyNotes, immediateSafetyFlag, confidence, "
            "citations, fallbackReason, pendingHumanReview, safetyFlags, disclaimer, and "
            "reviewStatus."
        ),
        "triageFallbackText": (
            "SafeSpeak cannot confidently triage this with the available information. General "
            "options may include documenting what happened, considering support services, and "
            "seeking official information if safe."
        ),
        "triageTemplateStatus": "approved",
    },
    "version": 1,
}


def _guardrails(language: str | None = None) -> dict[str, Any]:
    return {
        "informationOnly": True,
        "requiresHumanReview": True,
        "legalAdviceDisclaimer": (
            "This output is information-only and must not be treated as "
            "prescriptive legal advice."
        ),
        "language": language or "en",
    }


def _interaction(output: dict[str, Any]) -> dict[str, Any]:
    return {
        "interactionId": str(uuid4()),
        "output": output,
        "citations": output.get("citations", []),
        "guardrails": _guardrails(output.get("language") or output.get("targetLanguage")),
        "reviewStatus": "pending_human_review",
    }


def _owner_filter(principal: Principal) -> dict[str, ObjectId]:
    if principal.user_id and ObjectId.is_valid(principal.user_id):
        return {"userId": ObjectId(principal.user_id)}
    if principal.session_id and ObjectId.is_valid(principal.session_id):
        return {"sessionId": ObjectId(principal.session_id)}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication principal")


async def _get_owned_report(principal: Principal, report_id: str | None) -> dict[str, Any] | None:
    if not report_id or not ObjectId.is_valid(report_id):
        return None
    report = await get_database()["reports"].find_one(
        {
            "_id": ObjectId(report_id),
            **_owner_filter(principal),
            "deletedAt": {"$exists": False},
        }
    )
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


async def _get_report_evidence_citations(
    principal: Principal,
    report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not report:
        return []
    cursor = get_database()["evidences"].find(
        {
            "reportId": report["_id"],
            **_owner_filter(principal),
            "deletedAt": {"$exists": False},
        },
        {
            "_id": 1,
            "fileName": 1,
            "mimeType": 1,
            "sha256Hash": 1,
            "status": 1,
        },
    )
    evidence = await cursor.to_list(length=None)
    return [
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


def _report_citation(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not report:
        return []
    excerpt = report.get("originalNarrative") or report.get("context")
    return [
        {
            "sourceType": "report",
            "sourceId": str(report["_id"]),
            "title": report.get("refNo"),
            "excerpt": excerpt[:400] if isinstance(excerpt, str) else None,
        }
    ]


async def _build_report_context(
    principal: Principal | None,
    report_id: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not report_id:
        return None, []
    if principal is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")
    report = await _get_owned_report(principal, report_id)
    citations = _report_citation(report)
    citations.extend(await _get_report_evidence_citations(principal, report))
    return report, citations


def _interaction_with_citations(
    output: dict[str, Any],
    *,
    citations: list[dict[str, Any]],
    language: str | None = None,
) -> dict[str, Any]:
    return {
        "interactionId": str(uuid4()),
        "output": output,
        "citations": citations,
        "guardrails": _guardrails(language or output.get("language") or output.get("targetLanguage")),
        "reviewStatus": "pending_human_review",
    }


async def _get_public_platform_settings() -> dict[str, Any]:
    settings = await get_database()["platformsettings"].find_one({"key": "default"})
    if not settings:
        return deepcopy(DEFAULT_PLATFORM_SETTINGS)
    published = settings.get("published") or {}
    return {
        "ai": {
            **DEFAULT_PLATFORM_SETTINGS["ai"],
            **published.get("ai", {}),
        },
        "version": settings.get("version") or 1,
    }


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _string_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if items:
            return items[:8]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback or []


def _resource_recommendations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    recommendations: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title"))
        body = _text(item.get("body"))
        if not title or not body:
            continue
        recommendations.append(
            {
                "title": title,
                "body": body,
                "type": _text(item.get("type"), "support"),
            }
        )
    return recommendations[:6]


def _detect_any(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _triage_flags(
    narrative: str,
    structured_fields: dict[str, Any] | None,
    model_output: dict[str, Any],
) -> dict[str, bool]:
    structured_text = str(structured_fields or {})
    combined = f"{narrative}\n{structured_text}\n{model_output}"
    input_text = re.sub(r"[{}\[\]\":,_-]", " ", f"{narrative}\n{structured_text}").strip()
    return {
        "legalAdviceRisk": _detect_any(LEGAL_ADVICE_RISK_PATTERNS, combined),
        "clinicalAdviceRisk": _detect_any(CLINICAL_ADVICE_RISK_PATTERNS, combined),
        "crisisRisk": _detect_any(CRISIS_RISK_PATTERNS, combined),
        "insufficientInput": len(input_text) < 24,
    }


def _fallback_reason(flags: dict[str, bool]) -> str:
    if flags["crisisRisk"]:
        return "crisis_safety"
    if flags["legalAdviceRisk"]:
        return "legal_advice_risk"
    if flags["clinicalAdviceRisk"]:
        return "clinical_advice_risk"
    if flags["insufficientInput"]:
        return "insufficient_input"
    return "none"


def _pending_human_review(flags: dict[str, bool]) -> bool:
    return (
        flags["legalAdviceRisk"]
        or flags["clinicalAdviceRisk"]
        or flags["crisisRisk"]
        or flags["insufficientInput"]
    )


def _triage_confidence(value: Any, flags: dict[str, bool], citations: list[Any]) -> str:
    candidate = _text(value).lower()
    if _pending_human_review(flags):
        return "low"
    if candidate in {"low", "medium", "high"}:
        return candidate
    return "medium" if citations else "low"


def _triage_severity(value: Any, flags: dict[str, bool]) -> str:
    if flags["crisisRisk"]:
        return "urgent"
    candidate = _text(value).lower()
    return candidate if candidate in TRIAGE_SEVERITY_VALUES else "medium"


def _strip_disclaimer(text: str, disclaimer: str) -> str:
    return text.replace(disclaimer, "").strip()


def _normalize_speech_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:MAX_SPEECH_TEXT_LENGTH]


def _normalize_triage_output(
    *,
    model_output: dict[str, Any],
    narrative: str,
    structured_fields: dict[str, Any] | None,
    citations: list[Any],
    disclaimer: str = INFORMATION_ONLY_DISCLAIMER,
    human_review_note: str = "Review this with a qualified support worker before acting on it.",
    fallback_text: str = "SafeSpeak cannot confidently triage this with the available information.",
) -> dict[str, Any]:
    flags = _triage_flags(narrative, structured_fields, model_output)
    fallback_reason = _fallback_reason(flags)
    summary_fallback = (
        "Immediate safety may be a concern. If there is immediate danger, call 000 now."
        if fallback_reason == "crisis_safety"
        else fallback_text
    )
    assessment_fallback = (
        summary_fallback
        if fallback_reason == "none"
        else f"{summary_fallback} {human_review_note}"
    )
    summary = _strip_disclaimer(
        _text(model_output.get("summary"), summary_fallback), disclaimer
    )
    assessment_body = _strip_disclaimer(
        _text(model_output.get("assessmentBody"), assessment_fallback),
        disclaimer,
    )

    return {
        "severitySignal": _triage_severity(model_output.get("severitySignal"), flags),
        "primarySupportNeed": _text(model_output.get("primarySupportNeed"), "Support options"),
        "specialtyTag": _text(model_output.get("specialtyTag"), "general support").lower()[:80],
        "summary": summary or summary_fallback,
        "assessmentBody": assessment_body or assessment_fallback,
        "riskFactors": _string_list(model_output.get("riskFactors")),
        "suggestedSupportCategories": _string_list(
            model_output.get("suggestedSupportCategories"), ["support"]
        ),
        "recommendedActions": _string_list(
            model_output.get("recommendedActions"),
            [
                "Document what happened if safe to do so",
                "Consider contacting an official support service",
            ],
        ),
        "resourceRecommendations": _resource_recommendations(
            model_output.get("resourceRecommendations")
        ),
        "nonLegalSafetyNotes": _string_list(
            model_output.get("nonLegalSafetyNotes"), [disclaimer]
        ),
        "immediateSafetyFlag": flags["crisisRisk"]
        or bool(model_output.get("immediateSafetyFlag")),
        "confidence": _triage_confidence(model_output.get("confidence"), flags, citations),
        "citations": citations,
        "fallbackReason": fallback_reason,
        "pendingHumanReview": _pending_human_review(flags),
        "safetyFlags": flags,
        "disclaimer": disclaimer,
        "humanReviewNote": human_review_note,
        "reviewStatus": "pending_human_review",
    }


async def extract_incident_fields(
    request: ExtractIncidentFieldsInput,
    principal: Principal | None = None,
) -> dict[str, Any]:
    _report, citations = await _build_report_context(principal, request.reportId)
    output = await llm_service.json_completion(
        system=(
            "Extract incident fields as JSON with keys: incidentType, who, what, when, where, "
            "how, risks, evidenceMentioned, missingInformation, citations, reviewStatus. "
            "Do not guess. Use null or empty arrays when facts are absent."
        ),
        user=request.narrative,
        fallback={
            "incidentType": request.incidentCategory,
            "what": request.narrative,
            "missingInformation": ["Model unavailable; review the narrative manually."],
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction_with_citations(output, citations=citations, language=request.language)


async def clarifying_questions(
    request: ClarifyingQuestionsInput,
    principal: Principal | None = None,
) -> dict[str, Any]:
    _report, citations = await _build_report_context(principal, request.reportId)
    maximum = request.maxQuestions
    output = await llm_service.json_completion(
        system=(
            f"Generate as many trauma-informed clarifying questions as are genuinely needed "
            f"to understand this incident clearly, with an upper safety cap of {maximum} "
            "questions. Return JSON with keys: questions, rationale, citations, reviewStatus. "
            "The questions must be short, natural, supportive, and one at a time in tone. "
            "Do not ask for unnecessary identifying information."
        ),
        user=f"Narrative: {request.narrative}\nKnown fields: {request.structuredFields or {}}",
        fallback={
            "questions": ["When did this happen?", "Where did it happen?"][:maximum],
            "rationale": "Basic timeline details are missing.",
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction_with_citations(output, citations=citations, language=request.language)


async def generate_summary(
    request: GenerateSummaryInput,
    principal: Principal | None = None,
) -> dict[str, Any]:
    report, citations = await _build_report_context(principal, request.reportId)
    narrative = request.narrative
    if report and not narrative:
        narrative = report.get("originalNarrative")
    if report and not narrative:
        narrative = report.get("translatedNarrative") or ""
    structured_fields = request.structuredFields or (report.get("structuredFields") if report else {})
    output = await llm_service.json_completion(
        system=(
            "Create an information-only summary. Do not infer motives, diagnoses, crimes, or "
            "legal conclusions. Return JSON with summary, keyFacts, uncertaintyNotes, "
            "citations, reviewStatus."
        ),
        user=(
            f"Create an information-only summary for audience {request.audience}. "
            f"Narrative: {narrative or ''}\nFields: {structured_fields or {}}"
        ),
        fallback={
            "summary": narrative or "",
            "keyFacts": [],
            "uncertaintyNotes": ["Automated summarisation was unavailable."],
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction_with_citations(output, citations=citations, language=request.language)


async def triage_report(request: TriageInput, principal: Principal | None = None) -> dict[str, Any]:
    report, citations = await _build_report_context(principal, request.reportId)
    platform_settings = await _get_public_platform_settings()
    ai_settings = platform_settings["ai"]
    language = request.language or (report.get("language") if report else None)
    narrative = request.narrative or ""
    if report and not narrative:
        narrative = report.get("originalNarrative") or report.get("translatedNarrative") or ""
    structured_fields = request.structuredFields or (report.get("structuredFields") if report else None)
    output = await llm_service.json_completion(
        system=(
            f"{ai_settings['triageSystemPrompt']} "
            "Triage this report for information-only support. Return valid JSON only. "
            f"{ai_settings['triageResponseTemplate']} "
            "Use keys: severitySignal, primarySupportNeed, specialtyTag, summary, "
            "assessmentBody, riskFactors, suggestedSupportCategories, recommendedActions, "
            "resourceRecommendations, nonLegalSafetyNotes, immediateSafetyFlag, confidence, "
            "citations, fallbackReason, pendingHumanReview, safetyFlags, disclaimer, "
            "reviewStatus. severitySignal should be one of: low, medium, high, urgent."
        ),
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
            "reviewStatus": "pending_human_review",
        },
    )
    normalized = _normalize_triage_output(
        model_output=output,
        narrative=narrative,
        structured_fields=structured_fields,
        citations=citations,
        disclaimer=ai_settings["disclaimerText"],
        human_review_note=ai_settings["humanReviewText"],
        fallback_text=ai_settings["triageFallbackText"],
    )
    normalized["guardrails"] = _guardrails(language)
    normalized["interactionId"] = str(uuid4())
    normalized["model"] = get_settings().OPENAI_MODEL
    normalized["templateVersion"] = platform_settings["version"]
    normalized["templateStatus"] = ai_settings["triageTemplateStatus"]
    return normalized


async def translate(request: TranslateInput, _principal: Principal | None = None) -> dict[str, Any]:
    output = await llm_service.json_completion(
        system=(
            "Translate the text. Preserve meaning and tone. Return JSON with "
            "translatedText, sourceLanguage, targetLanguage, reviewStatus."
        ),
        user=(
            f"Source language: {request.sourceLanguage or 'auto-detect'}\n"
            f"Target language: {request.targetLanguage}\nText: {request.text}"
        ),
        fallback={
            "translatedText": request.text,
            "sourceLanguage": request.sourceLanguage,
            "targetLanguage": request.targetLanguage,
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction_with_citations(
        output,
        citations=[{"sourceType": "user_input", "excerpt": request.text[:400]}],
        language=request.targetLanguage,
    )


def redact_pii(request: RedactInput, _principal: Principal | None = None) -> dict[str, Any]:
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
                f"[{label}]"
                if request.replacementStyle == "labels"
                else "*" * len(match.group())
            )
            entities.append({"type": label, "start": match.start(), "end": match.end()})
            redacted = redacted[: match.start()] + replacement + redacted[match.end() :]
    return _interaction_with_citations(
        {
            "redactedText": redacted,
            "detectedEntities": entities,
            "replacementStyle": request.replacementStyle,
            "reviewStatus": "automated_review_required",
        },
        citations=[{"sourceType": "user_input", "excerpt": request.text[:400]}],
        language=request.language,
    )


async def transcribe_audio_file(
    request: TranscribeAudioInput,
    *,
    principal: Principal | None,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
) -> dict[str, Any]:
    if principal is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")
    settings = get_settings()
    if not file_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "audio file is required")
    if mime_type not in SUPPORTED_TRANSCRIPTION_MIME_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Unsupported audio/video file type for transcription",
        )
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "OPENAI_API_KEY is not configured",
        )

    files = {
        "file": (
            file_name or "audio-input.webm",
            file_bytes,
            mime_type,
        )
    }
    data = {"model": settings.OPENAI_TRANSCRIPTION_MODEL}
    if request.language:
        data["language"] = request.language

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            data=data,
            files=files,
        )

    if response.status_code >= 400:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "OpenAI transcription request failed",
        )

    payload = response.json()
    transcript = payload.get("text")
    if not isinstance(transcript, str) or not transcript.strip():
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "OpenAI transcription response was empty",
        )

    saved = request.saveTranscript is not False

    if request.evidenceId and saved:
        evidence = await get_database()["evidences"].find_one(
            {
                "_id": ObjectId(request.evidenceId),
                **_owner_filter(principal),
                "deletedAt": {"$exists": False},
            }
        )
        if not evidence:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
        await get_database()["evidences"].update_one(
            {"_id": evidence["_id"]},
            {
                "$set": {
                    "transcription": {
                        "text": transcript,
                        "language": payload.get("language"),
                        "model": settings.OPENAI_TRANSCRIPTION_MODEL,
                        "provider": "openai",
                        "transcribedAt": __import__("datetime").datetime.now(
                            __import__("datetime").UTC
                        ),
                        "transcribedBy": principal.user_id or principal.session_id,
                    }
                }
            },
        )

    if request.reportId:
        report = await _get_owned_report(principal, request.reportId)
        if not report:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
        if request.useAsNarrative:
            consent_snapshot = report.get("consentSnapshot") or {}
            if not consent_snapshot.get("cloud_sync"):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "cloud_sync consent is required to store transcription as report narrative",
                )
            await get_database()["reports"].update_one(
                {"_id": report["_id"]},
                {"$set": {"originalNarrative": transcript}},
            )
        else:
            structured_fields = report.get("structuredFields") or {}
            structured_fields["transcription"] = {
                "available": True,
                "language": payload.get("language"),
                "model": settings.OPENAI_TRANSCRIPTION_MODEL,
            }
            await get_database()["reports"].update_one(
                {"_id": report["_id"]},
                {"$set": {"structuredFields": structured_fields}},
            )

    return {
        "transcript": transcript,
        "language": payload.get("language"),
        "model": settings.OPENAI_TRANSCRIPTION_MODEL,
        "reportId": request.reportId,
        "evidenceId": request.evidenceId,
        "saved": saved,
    }


async def synthesize_speech(
    request: SynthesizeSpeechInput,
    _principal: Principal | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    text = _normalize_speech_text(request.text)
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "text is required")
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "OPENAI_API_KEY is not configured",
        )

    voice = request.voice or settings.OPENAI_TTS_VOICE
    async with httpx.AsyncClient(timeout=120.0) as client:
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
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "OpenAI speech synthesis request failed",
        )

    return {
        "audioBase64": base64.b64encode(response.content).decode("ascii"),
        "mimeType": "audio/mpeg",
        "model": settings.OPENAI_TTS_MODEL,
        "voice": voice,
        "temporary": True,
    }
