import re
from typing import Any

from .model import AI_REVIEW_STATUSES

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


def build_guardrails(language: str | None = None) -> dict[str, Any]:
    return {
        "informationOnly": True,
        "requiresHumanReview": True,
        "legalAdviceDisclaimer": (
            "This output is information-only and must not be treated as prescriptive legal advice."
        ),
        "language": language or "en",
    }


def detect_legal_advice_risk(text: str) -> bool:
    return any(pattern.search(text) for pattern in LEGAL_ADVICE_RISK_PATTERNS)


def detect_clinical_advice_risk(text: str) -> bool:
    return any(pattern.search(text) for pattern in CLINICAL_ADVICE_RISK_PATTERNS)


def detect_crisis_risk(text: str) -> bool:
    return any(pattern.search(text) for pattern in CRISIS_RISK_PATTERNS)


def should_require_human_review(text: str) -> bool:
    return (
        detect_legal_advice_risk(text)
        or detect_clinical_advice_risk(text)
        or detect_crisis_risk(text)
    )


def enforce_ai_output_guardrails(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def validate_safe_speak_response(text: str) -> dict[str, bool]:
    return {
        "legalAdviceRisk": detect_legal_advice_risk(text),
        "clinicalAdviceRisk": detect_clinical_advice_risk(text),
        "crisisRisk": detect_crisis_risk(text),
        "requiresHumanReview": should_require_human_review(text),
    }


def build_guardrail_revision_instruction() -> str:
    return (
        "Revise the response so it stays information-only, avoids legal or clinical advice, "
        "and asks at most one minimal next question."
    )


def build_compact_retry_instruction() -> str:
    return (
        "Retry with concise JSON only, preserve trauma-informed tone, and do not add legal advice."
    )


def normalize_triage_output(
    *,
    model_output: dict[str, Any],
    narrative: str,
    structured_fields: dict[str, Any] | None,
    citations: list[Any],
    disclaimer: str,
    human_review_note: str,
    fallback_text: str,
) -> dict[str, Any]:
    combined = f"{narrative}\n{structured_fields or {}}\n{model_output}"
    legal_risk = detect_legal_advice_risk(combined)
    clinical_risk = detect_clinical_advice_risk(combined)
    crisis_risk = detect_crisis_risk(combined)
    input_text = re.sub(r"[{}\[\]\":,_-]", " ", f"{narrative}\n{structured_fields or {}}").strip()
    insufficient_input = len(input_text) < 24
    fallback_reason = "none"
    if crisis_risk:
        fallback_reason = "crisis_safety"
    elif legal_risk:
        fallback_reason = "legal_advice_risk"
    elif clinical_risk:
        fallback_reason = "clinical_advice_risk"
    elif insufficient_input:
        fallback_reason = "insufficient_input"

    summary_fallback = (
        "Immediate safety may be a concern. If there is immediate danger, call 000 now."
        if fallback_reason == "crisis_safety"
        else fallback_text
    )
    assessment_fallback = (
        summary_fallback if fallback_reason == "none" else f"{summary_fallback} {human_review_note}"
    )
    summary = enforce_ai_output_guardrails(str(model_output.get("summary") or "")).replace(
        disclaimer, ""
    )
    assessment_body = enforce_ai_output_guardrails(
        str(model_output.get("assessmentBody") or "")
    ).replace(disclaimer, "")
    pending_review = legal_risk or clinical_risk or crisis_risk or insufficient_input
    confidence = str(model_output.get("confidence") or "").strip().lower()
    if pending_review:
        confidence = "low"
    elif confidence not in {"low", "medium", "high"}:
        confidence = "medium" if citations else "low"

    severity_signal = str(model_output.get("severitySignal") or "").strip().lower()
    if crisis_risk:
        severity_signal = "urgent"
    elif severity_signal not in TRIAGE_SEVERITY_VALUES:
        severity_signal = "medium"

    def _string_list(value: Any, fallback: list[str] | None = None) -> list[str]:
        if isinstance(value, list):
            items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            if items:
                return items[:8]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return fallback or []

    resource_recommendations = []
    if isinstance(model_output.get("resourceRecommendations"), list):
        for item in model_output["resourceRecommendations"]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            body = str(item.get("body") or "").strip()
            if not title or not body:
                continue
            resource_recommendations.append(
                {
                    "title": title,
                    "body": body,
                    "type": str(item.get("type") or "support").strip() or "support",
                }
            )

    return {
        "severitySignal": severity_signal,
        "primarySupportNeed": str(model_output.get("primarySupportNeed") or "Support options"),
        "specialtyTag": str(model_output.get("specialtyTag") or "general support").lower()[:80],
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
        "resourceRecommendations": resource_recommendations[:6],
        "nonLegalSafetyNotes": _string_list(model_output.get("nonLegalSafetyNotes"), [disclaimer]),
        "immediateSafetyFlag": crisis_risk or bool(model_output.get("immediateSafetyFlag")),
        "confidence": confidence,
        "citations": citations,
        "fallbackReason": fallback_reason,
        "pendingHumanReview": pending_review,
        "safetyFlags": {
            "legalAdviceRisk": legal_risk,
            "clinicalAdviceRisk": clinical_risk,
            "crisisRisk": crisis_risk,
            "insufficientInput": insufficient_input,
        },
        "disclaimer": disclaimer,
        "humanReviewNote": human_review_note,
        "reviewStatus": AI_REVIEW_STATUSES["pendingHumanReview"],
    }
