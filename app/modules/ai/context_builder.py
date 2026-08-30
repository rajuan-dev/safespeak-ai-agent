from typing import Any


def build_active_incident_summary(facts: dict[str, Any] | None) -> str:
    if not facts:
        return ""
    timeline = facts.get("timeline") or {}
    ordered = [
        timeline.get(key) for key in ("what", "when", "where", "who", "safety") if timeline.get(key)
    ]
    return " | ".join(ordered[:5])


def build_classifier_metadata(classification: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": classification.get("intent"),
        "confidence": classification.get("confidence"),
        "matchedPatterns": classification.get("matchedPatterns") or [],
    }


def build_safe_speak_context(
    *,
    session: dict[str, Any],
    messages: list[dict[str, Any]],
    facts: dict[str, Any] | None,
    classification: dict[str, Any],
    consent: dict[str, bool],
) -> dict[str, Any]:
    return {
        "selectedTopic": session.get("selectedTopic"),
        "detectedCategory": session.get("detectedCategory"),
        "messageCount": session.get("messageCount", 0),
        "latestTurnRiskLevel": session.get("latestTurnRiskLevel"),
        "activeIncidentSummary": build_active_incident_summary(facts),
        "recentMessages": [item.get("content") for item in messages[-4:] if item.get("content")],
        "classifier": build_classifier_metadata(classification),
        "consent": {
            "processWithAi": bool(consent.get("process_with_ai")),
            "storeLocal": bool(consent.get("store_local")),
            "cloudSync": bool(consent.get("cloud_sync")),
            "analytics": bool(consent.get("anonymised_analytics")),
        },
    }
