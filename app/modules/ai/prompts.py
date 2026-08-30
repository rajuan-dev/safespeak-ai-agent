from typing import Any

from .model import SAFE_SPEAK_INFORMATION_ONLY_DISCLAIMER

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


def build_information_only_disclaimer() -> str:
    return SAFE_SPEAK_INFORMATION_ONLY_DISCLAIMER


def build_extract_prompt() -> str:
    return (
        "Extract incident fields as JSON with keys: incidentType, who, what, when, where, "
        "how, risks, evidenceMentioned, missingInformation, citations, reviewStatus. "
        "Do not guess. Use null or empty arrays when facts are absent."
    )


def build_clarifying_prompt(maximum: int) -> str:
    return (
        f"Generate as many trauma-informed clarifying questions as are genuinely needed "
        f"to understand this incident clearly, with an upper safety cap of {maximum} "
        "questions. Return JSON with keys: questions, rationale, citations, reviewStatus. "
        "The questions must be short, natural, supportive, and one at a time in tone. "
        "Do not ask for unnecessary identifying information."
    )


def build_summary_prompt() -> str:
    return (
        "Create an information-only summary. Do not infer motives, diagnoses, crimes, or "
        "legal conclusions. Return JSON with summary, keyFacts, uncertaintyNotes, "
        "citations, reviewStatus."
    )


def build_translate_prompt() -> str:
    return (
        "Translate the text. Preserve meaning and tone. Return JSON with "
        "translatedText, sourceLanguage, targetLanguage, reviewStatus."
    )


def build_triage_prompt(ai_settings: dict[str, Any]) -> str:
    return (
        f"{ai_settings['triageSystemPrompt']} "
        "Triage this report for information-only support. Return valid JSON only. "
        f"{ai_settings['triageResponseTemplate']} "
        "Use keys: severitySignal, primarySupportNeed, specialtyTag, summary, "
        "assessmentBody, riskFactors, suggestedSupportCategories, recommendedActions, "
        "resourceRecommendations, nonLegalSafetyNotes, immediateSafetyFlag, confidence, "
        "citations, fallbackReason, pendingHumanReview, safetyFlags, disclaimer, "
        "reviewStatus. severitySignal should be one of: low, medium, high, urgent."
    )


def build_conversation_prompt(context: dict[str, Any]) -> str:
    return (
        "You are SafeSpeak's trauma-informed conversation assistant. "
        "Respond with supportive, minimal-question guidance. Do not interrogate, "
        "do not give legal advice, and prioritize immediate safety. "
        "Return JSON with assistantMessage, nextQuestion, confidence, intent, "
        "responseMode, selectedResponseSource, responseSource, reviewStatus, "
        "assistantLanguage, triageUpdated, latestTurnRiskLevel, "
        "activeIncidentRiskLevel, sessionHistoricalMaxRiskLevel, showSources, rag. "
        f"Context summary: {context.get('activeIncidentSummary') or 'none'}"
    )
