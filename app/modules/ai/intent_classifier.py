import re
from typing import Any

INTENT_PATTERNS = {
    "safety_crisis": (r"\bunsafe\b", r"\bdanger\b", r"\bemergency\b", r"\bthreat\w*\b"),
    "physical_harm": (r"\bhit\b", r"\bassault\b", r"\bviolence\b", r"\binjur\w*\b"),
    "incident_disclosure": (r"\bhappened\b", r"\bsaid\b", r"\bdid\b", r"\bshared\b"),
    "evidence_upload": (r"\bevidence\b", r"\bphoto\b", r"\bvideo\b", r"\brecording\b"),
    "legal_boundary_specific_case": (r"\bsue\b", r"\billegal\b", r"\bcase\b"),
    "language_or_translation": (r"\btranslate\b", r"\blanguage\b", r"\benglish\b"),
    "scam_check": (r"\bscam\b", r"\bfraud\b", r"\botp\b", r"\bbank\b"),
    "meta_feedback": (r"\byou are helpful\b", r"\bthat response\b", r"\bnot useful\b"),
}


def classify_safe_speak_intent_details(message: str) -> dict[str, Any]:
    lowered = (message or "").lower()
    for intent, patterns in INTENT_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            return {"intent": intent, "confidence": "medium", "matchedPatterns": list(patterns)}
    return {"intent": "general_conversation", "confidence": "low", "matchedPatterns": []}


def classify_safe_speak_intent(message: str) -> str:
    return classify_safe_speak_intent_details(message)["intent"]


def detect_meta_feedback_or_capability_question(message: str) -> bool:
    intent = classify_safe_speak_intent(message)
    return intent in {"meta_feedback", "language_or_translation"}
