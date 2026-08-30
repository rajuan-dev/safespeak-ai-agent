import re
from typing import Any

CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "domestic_violence": (
        "partner",
        "family violence",
        "domestic violence",
        "coercive",
        "husband",
        "wife",
    ),
    "workplace_bullying": (
        "manager",
        "boss",
        "workplace",
        "work",
        "coworker",
        "office",
        "hr",
        "bully",
        "bullying",
    ),
    "racism_discrimination": ("racist", "racism", "discrimination", "hate", "slur"),
    "online_abuse": ("online", "instagram", "facebook", "tiktok", "threatened to post"),
    "scam_fraud": ("scam", "fraud", "phishing", "otp", "bank details", "fake link"),
    "theft_property": ("stole", "robbed", "wallet", "phone", "bag"),
    "harassment": ("harassment", "stalking", "followed", "intimidated", "threatened"),
    "mental_health_distress": ("anxious", "panic", "depressed", "overwhelmed", "cope"),
}


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_timeline(content: str) -> dict[str, str]:
    lowered = content.lower()
    timeline: dict[str, str] = {}
    if " at " in lowered or " work" in lowered or " school" in lowered or " home" in lowered:
        timeline["where"] = collapse_whitespace(content)
    if any(token in lowered for token in ("today", "yesterday", "last night", "this morning")):
        timeline["when"] = collapse_whitespace(content)
    if any(
        token in lowered
        for token in (
            "partner",
            "manager",
            "boss",
            "friend",
            "stranger",
            "coworker",
            "teacher",
        )
    ):
        timeline["who"] = collapse_whitespace(content)
    if any(
        token in lowered
        for token in ("hurt", "threat", "scam", "stole", "abuse", "harass", "bully", "leak")
    ):
        timeline["what"] = collapse_whitespace(content)
    if any(
        token in lowered
        for token in ("unsafe", "danger", "afraid", "scared", "emergency", "help now")
    ):
        timeline["safety"] = collapse_whitespace(content)
    return timeline


def detect_category(
    messages: list[dict[str, Any]], selected_topic: str | None
) -> tuple[str, float]:
    combined = " ".join(message.get("content", "") for message in messages).lower()
    if selected_topic == "scamshield":
        return "scam_fraud", 0.85
    best_category = "general_support"
    best_score = 0.3
    for category, keywords in CATEGORY_PATTERNS.items():
        score = sum(1 for keyword in keywords if keyword in combined)
        if score > 0 and score / len(keywords) > best_score:
            best_category = category
            best_score = min(0.95, 0.35 + (score / len(keywords)))
    return best_category, round(best_score, 2)


def detect_risk_level(messages: list[dict[str, Any]], facts: dict[str, Any]) -> str:
    combined = " ".join(message.get("content", "") for message in messages).lower()
    if any(token in combined for token in ("immediate danger", "call 000", "kill", "suicide")):
        return "immediate"
    if any(token in combined for token in ("weapon", "hit", "hurt", "threat", "unsafe")):
        return "high"
    if any(token in combined for token in ("scared", "panic", "stole", "harass", "racist")):
        return "medium"
    if facts.get("safetyConcerns"):
        return "medium"
    return "low"


def build_missing_information(facts: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not facts.get("whatHappened"):
        missing.append("what_details")
    if not facts.get("whenHappened"):
        missing.append("when_details")
    if not facts.get("whereHappened"):
        missing.append("where_details")
    return missing


def can_offer_triage(user_turn_count: int, facts: dict[str, Any], confidence_score: float) -> bool:
    populated_fields = sum(
        1
        for key in ("whatHappened", "whenHappened", "whereHappened", "peopleInvolved")
        if facts.get(key)
    )
    return user_turn_count >= 1 and confidence_score >= 0.45 and populated_fields >= 2


def can_proceed_to_recommendations(
    facts: dict[str, Any], category: str, confidence_score: float
) -> bool:
    return (
        category != "general_support"
        and confidence_score >= 0.45
        and bool(facts.get("whatHappened"))
        and bool(
            facts.get("whenHappened")
            or facts.get("whereHappened")
            or facts.get("peopleInvolved")
        )
    )


def build_reasoning_summary(category: str, risk_level: str, facts: dict[str, Any]) -> str:
    parts = [f"SafeSpeak sees this as {category.replace('_', ' ')}."]
    if risk_level in {"high", "immediate"}:
        parts.append("Immediate safety support should stay in focus.")
    if facts.get("whatHappened"):
        parts.append("There is enough context to start a guided triage summary.")
    else:
        parts.append("More context is still needed before stronger routing is shown.")
    return " ".join(parts)


def build_support_actions(category: str, risk_level: str) -> list[dict[str, Any]]:
    actions = [
        {
            "slot": "primarySupport",
            "title": "Review support options",
            "description": "Look at the support and reporting pathways that match this triage.",
            "whySuggested": "Suggested from your current triage pathway.",
            "href": "/dashboard?view=reportsubmissionrecommendations",
            "actionKind": "external_link",
            "consentNote": "Nothing is shared automatically.",
            "urgency": "high" if risk_level in {"high", "immediate"} else "medium",
            "enabled": True,
        },
        {
            "slot": "secondarySupport",
            "title": "Prepare an information-only summary",
            "description": (
                "You can review a draft summary before deciding whether to report anything."
            ),
            "whySuggested": "This keeps control with you.",
            "href": "/dashboard?view=reportsubmissionreview",
            "actionKind": "external_link",
            "consentNote": "You choose if anything is shared later.",
            "urgency": "medium",
            "enabled": True,
        },
    ]
    if risk_level == "immediate":
        actions.insert(
            0,
            {
                "slot": "immediateDanger",
                "title": "Get immediate safety support",
                "description": (
                    "If there is immediate danger, emergency help may be the safest next step."
                ),
                "whySuggested": "The conversation includes urgent safety indicators.",
                "href": "tel:000",
                "actionKind": "call",
                "consentNote": "This is only shown as an option.",
                "urgency": "urgent",
                "enabled": True,
            },
        )
    if category == "scam_fraud":
        actions.append(
            {
                "slot": "additional",
                "title": "Secure your accounts",
                "description": (
                    "Change passwords and contact your bank if financial details may be exposed."
                ),
                "whySuggested": "Scam-related harm often requires quick account protection.",
                "href": "/dashboard?view=scamshield",
                "actionKind": "external_link",
                "consentNote": "Nothing is shared automatically.",
                "urgency": "high" if risk_level != "low" else "medium",
                "enabled": True,
            }
        )
    return actions


def build_report_timeline(facts: dict[str, Any]) -> list[dict[str, str]]:
    timeline = []
    for key, label in (
        ("whatHappened", "What happened"),
        ("whenHappened", "When"),
        ("whereHappened", "Where"),
        ("peopleInvolved", "People involved"),
    ):
        if facts.get(key):
            timeline.append({"label": label, "value": str(facts[key])})
    return timeline
