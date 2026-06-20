import re
from typing import Any
from uuid import uuid4

from app.models.ai import NarrativeInput, RedactInput, TranslateInput, TriageInput
from app.services.llm import llm_service


def _interaction(output: dict[str, Any]) -> dict[str, Any]:
    return {
        "interactionId": str(uuid4()),
        "output": output,
        "citations": output.get("citations", []),
        "guardrails": {"informationOnly": True},
        "reviewStatus": output.get("reviewStatus", "generated"),
    }


async def extract_incident_fields(request: NarrativeInput) -> dict[str, Any]:
    output = await llm_service.json_completion(
        system=(
            "Extract incident facts without guessing. Return JSON with incidentType, who, what, "
            "when, where, how, risks, evidenceMentioned, missingInformation, reviewStatus. "
            "Use null or empty arrays when facts are absent."
        ),
        user=request.narrative,
        fallback={
            "incidentType": request.incidentCategory,
            "what": request.narrative,
            "missingInformation": ["Model unavailable; review the narrative manually."],
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction(output)


async def clarifying_questions(request: NarrativeInput) -> dict[str, Any]:
    maximum = request.maxQuestions or 3
    output = await llm_service.json_completion(
        system=(
            f"Create at most {maximum} trauma-informed clarifying questions. Do not ask for "
            "unnecessary identifying information. Return JSON with questions, rationale, "
            "reviewStatus."
        ),
        user=f"Narrative: {request.narrative}\nKnown fields: {request.structuredFields or {}}",
        fallback={
            "questions": ["When did this happen?", "Where did it happen?"][:maximum],
            "rationale": "Basic timeline details are missing.",
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction(output)


async def generate_summary(request: NarrativeInput) -> dict[str, Any]:
    output = await llm_service.json_completion(
        system=(
            "Create a neutral factual incident summary. Do not infer motives, diagnoses, crimes, "
            "or legal conclusions. Return JSON with summary, keyFacts, uncertaintyNotes, "
            "reviewStatus."
        ),
        user=f"Narrative: {request.narrative}\nFields: {request.structuredFields or {}}",
        fallback={
            "summary": request.narrative,
            "keyFacts": [],
            "uncertaintyNotes": ["Automated summarisation was unavailable."],
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction(output)


async def triage_report(request: TriageInput) -> dict[str, Any]:
    narrative = request.narrative or ""
    output = await llm_service.json_completion(
        system=(
            "Provide non-diagnostic, trauma-informed support triage. Return JSON with "
            "severitySignal, primarySupportNeed, specialtyTag, summary, assessmentBody, "
            "riskFactors, suggestedSupportCategories, recommendedActions, "
            "resourceRecommendations, nonLegalSafetyNotes, immediateSafetyFlag, confidence, "
            "pendingHumanReview, reviewStatus. Never claim a legal or clinical determination. "
            "If immediate danger is described, recommend calling 000 in Australia."
        ),
        user=f"Narrative: {narrative}\nStructured fields: {request.structuredFields or {}}",
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
    output.setdefault("interactionId", str(uuid4()))
    output.setdefault("disclaimer", "This is support triage, not legal or clinical advice.")
    output.setdefault("citations", [])
    output.setdefault("safetyFlags", {})
    return output


async def translate(request: TranslateInput) -> dict[str, Any]:
    output = await llm_service.json_completion(
        system=(
            "Translate faithfully without adding or omitting facts. Return JSON with "
            "translatedText, sourceLanguage, targetLanguage, reviewStatus."
        ),
        user=(
            f"Source language: {request.sourceLanguage or 'detect'}\n"
            f"Target language: {request.targetLanguage}\nText: {request.text}"
        ),
        fallback={
            "translatedText": request.text,
            "sourceLanguage": request.sourceLanguage,
            "targetLanguage": request.targetLanguage,
            "reviewStatus": "pending_human_review",
        },
    )
    return _interaction(output)


def redact_pii(request: RedactInput) -> dict[str, Any]:
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
    return _interaction(
        {
            "redactedText": redacted,
            "detectedEntities": entities,
            "replacementStyle": request.replacementStyle,
            "reviewStatus": "automated_review_required",
        }
    )
