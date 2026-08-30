from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from bson import ObjectId
from fastapi import HTTPException, status

from app.modules.ai.service import get_conversation_assistant as get_ai_conversation_assistant
from app.modules.audit.service import create_audit_log
from app.modules.consent.service import get_current_consent

from .model import CONVERSATION_FLOW_ACTIONS
from .repository import ConversationFlowRepository, get_conversation_flow_repository
from .schema import AppendConversationFlowMessageInput, CreateConversationFlowSessionInput
from .state_machine import (
    build_missing_information,
    build_reasoning_summary,
    build_report_timeline,
    build_support_actions,
    can_offer_triage,
    can_proceed_to_recommendations,
    detect_category,
    detect_risk_level,
    extract_timeline,
)


class ConversationAssistantPort(Protocol):
    async def respond(
        self,
        *,
        session: dict[str, Any],
        messages: list[dict[str, Any]],
        latest_user_message: str,
        language: str,
        consent: dict[str, bool],
    ) -> dict[str, Any]: ...


def get_conversation_assistant() -> ConversationAssistantPort:
    return get_ai_conversation_assistant()


def _owner_filter(owner: dict[str, str | None]) -> dict[str, str]:
    if owner.get("userId"):
        return {"userId": owner["userId"]}
    if owner.get("sessionId"):
        return {"sessionId": owner["sessionId"]}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _session_record(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(session["_id"]),
        "selectedTopic": session.get("selectedTopic"),
        "detectedCategory": session.get("detectedCategory"),
        "detectedLanguage": session.get("detectedLanguage"),
        "status": session.get("status"),
        "safetyRiskLevel": session.get("safetyRiskLevel"),
        "activeIssueId": session.get("activeIssueId"),
        "latestTurnRiskLevel": session.get("latestTurnRiskLevel"),
        "activeIncidentRiskLevel": session.get("activeIncidentRiskLevel"),
        "sessionHistoricalMaxRiskLevel": session.get("sessionHistoricalMaxRiskLevel"),
        "assistantFormatPreference": session.get("assistantFormatPreference"),
        "jurisdiction": session.get("jurisdiction"),
        "location": session.get("location"),
        "messageCount": session.get("messageCount", 0),
        "userTurnCount": session.get("userTurnCount", 0),
        "triageOfferedAt": _serialize_value(session.get("triageOfferedAt")),
        "createdAt": _serialize_value(session.get("createdAt")),
        "updatedAt": _serialize_value(session.get("updatedAt")),
    }


def _message_record(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(message["_id"]),
        "role": message.get("role"),
        "content": message.get("content"),
        "turnNumber": message.get("turnNumber"),
        "metadata": _serialize_value(message.get("metadata") or {}),
        "createdAt": _serialize_value(message.get("createdAt")),
        "updatedAt": _serialize_value(message.get("updatedAt")),
    }


def _facts_record(facts: dict[str, Any] | None) -> dict[str, Any] | None:
    if not facts:
        return None
    result = _serialize_value(facts)
    if "_id" in result:
        result["_id"] = str(result["_id"])
    if "conversationSessionId" in result:
        result["conversationSessionId"] = str(result["conversationSessionId"])
    return result


def _category_label(category: str) -> str:
    return category.replace("_", " ").title()


def _triage_record(triage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not triage:
        return None
    structured = dict(triage.get("structuredFacts") or {})
    return {
        "likelyCategory": triage.get("likelyCategory"),
        "likelyCategoryLabel": _category_label(triage.get("likelyCategory") or "general_support"),
        "confidenceScore": triage.get("confidenceScore", 0),
        "confidenceLabel": "high" if (triage.get("confidenceScore") or 0) >= 0.75 else "medium",
        "safetyRiskLevel": triage.get("safetyRiskLevel", "low"),
        "reasoningSummary": triage.get("reasoningSummary"),
        "structuredFacts": structured,
        "matchedLegislationIds": triage.get("matchedLegislationIds") or [],
        "matchedKnowledgeSources": triage.get("matchedKnowledgeSources") or [],
        "humanReviewRecommended": triage.get("humanReviewRecommended", False),
        "missingInformation": triage.get("missingInformation") or [],
        "canProceedToRecommendations": triage.get("canProceedToRecommendations", False),
        "matchedResourceTypes": triage.get("matchedResourceTypes") or [],
        "relatedIssueTypes": triage.get("relatedIssueTypes") or [],
        "presentation": {
            "title": _category_label(triage.get("likelyCategory") or "general_support"),
            "body": triage.get("reasoningSummary"),
            "assessmentNote": "SafeSpeak is showing options, not making decisions for you.",
            "primaryStepTitle": "Continue when you are ready",
            "primaryStepBody": "You can review support, reporting, evidence, and safety steps.",
            "immediateDangerBody": "If there is immediate danger, emergency help may be safest.",
            "secondTitle": "Support options",
            "secondBody": "You can review broad support pathways without sending anything.",
            "secondActionLabel": "Review support",
            "secondActionHref": "/dashboard?view=reportsubmissionsupport",
            "thirdTitle": "Recommendations",
            "thirdBody": "You can also look at recommended next steps from this triage.",
            "thirdActionLabel": "Review recommendations",
            "thirdActionHref": "/dashboard?view=reportsubmissionrecommendations",
            "stepReasons": triage.get("missingInformation") or [],
            "microCardSummary": "Suggested learning cards are selected from the current triage.",
        },
        "disclaimer": "This is information only, not legal advice.",
    }


async def _audit(
    context: dict[str, Any],
    action: str,
    resource_id: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    owner = context["owner"]
    await create_audit_log(
        actor_type="user" if owner.get("userId") else "anonymous_session",
        actor_id=owner.get("userId"),
        session_id=owner.get("sessionId"),
        action=action,
        resource_type="session",
        resource_id=resource_id,
        ip=context.get("ip"),
        user_agent=context.get("userAgent"),
        metadata=metadata or {},
    )


async def _require_storage_consent(owner: dict[str, str | None]) -> dict[str, bool]:
    consent = await get_current_consent(owner)
    if not consent.get("store_local") and not consent.get("cloud_sync"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "store_local or cloud_sync consent is required before conversation data can be stored",
        )
    return consent


async def _get_owned_session(
    context: dict[str, Any],
    conversation_session_id: str,
    *,
    repository: ConversationFlowRepository,
) -> dict[str, Any]:
    session = await repository.find_session_for_owner(conversation_session_id, context["owner"])
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation session not found")
    return session


def _merge_timeline(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    return {**existing, **{key: value for key, value in incoming.items() if value}}


def _facts_from_timeline(timeline: dict[str, str]) -> dict[str, Any]:
    return {
        "whatHappened": timeline.get("what"),
        "whenHappened": timeline.get("when"),
        "whereHappened": timeline.get("where"),
        "peopleInvolved": timeline.get("who"),
        "safetyConcerns": timeline.get("safety"),
        "evidenceMentioned": timeline.get("evidence"),
        "emotionalState": timeline.get("emotion"),
        "extractedEvents": [value for value in timeline.values()][:6],
        "missingInformation": [],
        "timeline": timeline,
    }


async def _build_triage(
    session: dict[str, Any],
    messages: list[dict[str, Any]],
    facts: dict[str, Any] | None,
    *,
    repository: ConversationFlowRepository,
    finalize_session: bool = False,
) -> dict[str, Any]:
    facts = facts or {}
    category, confidence_score = detect_category(messages, session.get("selectedTopic"))
    risk_level = detect_risk_level(messages, facts)
    missing_information = build_missing_information(facts)
    triage_payload = {
        "likelyCategory": category,
        "confidenceScore": confidence_score,
        "safetyRiskLevel": risk_level,
        "reasoningSummary": build_reasoning_summary(category, risk_level, facts),
        "structuredFacts": {
            "matchedFacts": list((facts.get("timeline") or {}).keys()),
            "organisations": [],
            "platforms": [],
            "protectedAttributes": [],
            "jurisdiction": session.get("jurisdiction"),
            "immediateDanger": risk_level == "immediate",
            "threatsPresent": risk_level in {"high", "immediate"},
            "evidenceAvailable": bool(facts.get("evidenceMentioned")),
        },
        "matchedLegislationIds": [],
        "matchedKnowledgeSources": [],
        "humanReviewRecommended": confidence_score < 0.6,
        "missingInformation": missing_information,
        "canProceedToRecommendations": can_proceed_to_recommendations(
            facts, category, confidence_score
        ),
        "matchedResourceTypes": [category, "support"],
        "relatedIssueTypes": [category],
    }
    triage = await repository.upsert_triage(str(session["_id"]), triage_payload)
    session_updates = {
        "detectedCategory": category,
        "detectedLanguage": session.get("detectedLanguage") or "en",
        "safetyRiskLevel": risk_level,
        "activeIncidentRiskLevel": risk_level,
        "sessionHistoricalMaxRiskLevel": risk_level,
    }
    if finalize_session and triage_payload["canProceedToRecommendations"]:
        session_updates["status"] = "triaged"
    await repository.update_session(
        str(session["_id"]),
        _owner_filter_from_session(session),
        session_updates,
    )
    refreshed = await repository.find_session_for_owner(
        str(session["_id"]), _owner_filter_from_session(session)
    )
    if refreshed:
        session = refreshed
    return triage or triage_payload


def _owner_filter_from_session(session: dict[str, Any]) -> dict[str, str | None]:
    return {
        "userId": str(session["userId"]) if session.get("userId") else None,
        "sessionId": str(session["sessionId"]) if session.get("sessionId") else None,
    }


def _recommendations_for_triage(
    triage: dict[str, Any], jurisdiction: str | None
) -> list[dict[str, Any]]:
    category = triage.get("likelyCategory") or "general_support"
    label = _category_label(category)
    return [
        {
            "id": f"{category}-support",
            "title": f"{label} support options",
            "description": (
                "Review support and reporting pathways without sending anything automatically."
            ),
            "category": category,
            "resourceType": "support",
            "ctaLabel": "Review options",
            "websiteUrl": "/dashboard?view=reportsubmissionrecommendations",
            "priority": 100,
            "jurisdiction": jurisdiction or "AU",
            "active": True,
        },
        {
            "id": f"{category}-evidence",
            "title": "Evidence and documentation guidance",
            "description": "Keep only the details that feel necessary for your next step.",
            "category": category,
            "resourceType": "evidence_guidance",
            "ctaLabel": "Review guidance",
            "websiteUrl": "/dashboard?view=reportsubmissionevidence",
            "priority": 90,
            "jurisdiction": jurisdiction or "AU",
            "active": True,
        },
    ]


def _support_bundle(
    session: dict[str, Any], triage: dict[str, Any], facts: dict[str, Any] | None
) -> dict[str, Any]:
    category = triage.get("likelyCategory") or "general_support"
    risk_level = triage.get("safetyRiskLevel") or "low"
    actions = build_support_actions(category, risk_level)
    recommendations = _recommendations_for_triage(triage, session.get("jurisdiction"))
    intake_plan = {
        "pathwayId": category,
        "requiredFields": [{"key": "whatHappened", "label": "What happened"}],
        "optionalFields": [
            {"key": "whenHappened", "label": "When"},
            {"key": "whereHappened", "label": "Where"},
        ],
        "safetyWarnings": (
            ["Immediate safety may need attention first."] if risk_level == "immediate" else []
        ),
        "consentRequiredBeforeSharing": True,
        "userFriendlyExplanation": "SafeSpeak keeps this as a guided intake, not a forced report.",
    }
    return {
        "suggestedMicroCardIds": [category, "general_support"],
        "recommendedActions": [action for action in actions if action["slot"] != "additional"][:3],
        "additionalResources": [action for action in actions if action["slot"] == "additional"][:6],
        "matchedSupportServices": recommendations,
        "fallbackUsed": True,
        "possiblePathways": [
            {
                "pathwayId": category,
                "title": _category_label(category),
                "description": "A broad support pathway based on the current conversation.",
                "userFacingLabel": "Review your options",
                "userFacingIntro": (
                    "You can explore options before deciding on any report or referral."
                ),
                "relatedCategory": category,
            }
        ],
        "intakePlan": intake_plan,
        "intakePlans": [intake_plan],
        "consentGovernance": {
            "nothingSharedAutomatically": True,
            "userChoosesWhatToDoNext": True,
            "reviewWithoutSending": True,
            "consentRequiredBeforeSharing": True,
            "consentRequiredBeforeReferral": True,
            "consentRequiredBeforeExport": True,
            "consentRequiredBeforeEvidenceUpload": True,
            "consentRequiredBeforeCloudSync": True,
            "noAutomaticPoliceEscalation": True,
            "noBackgroundTracking": True,
            "messages": [
                "Nothing is shared automatically.",
                "You choose what happens next.",
                "You can review options before sending anything.",
            ],
        },
        "reportPreparation": {
            "status": "draft",
            "informationOnlyDisclaimer": "This is information only, not legal advice.",
            "consentState": "not_granted",
            "notSentYet": True,
            "userNarrativeSummary": facts.get("whatHappened") if facts else "",
            "structuredFactsSummary": list((facts or {}).get("timeline", {}).keys()),
            "timeline": build_report_timeline(facts or {}),
            "evidenceList": [],
            "selectedPathwayId": category,
            "missingFields": triage.get("missingInformation") or [],
        },
    }


def _details_payload(
    triage: dict[str, Any], recommendations: list[dict[str, Any]], facts: dict[str, Any] | None
) -> dict[str, Any]:
    category = triage.get("likelyCategory") or "general_support"
    serialized_facts = _serialize_value(facts or {})
    return {
        "category": category,
        "categoryLabel": _category_label(category),
        "safetyRiskLevel": triage.get("safetyRiskLevel") or "low",
        "matchedKnowledgeSources": triage.get("matchedKnowledgeSources") or [],
        "matchedLegislationIds": triage.get("matchedLegislationIds") or [],
        "humanReviewRecommended": triage.get("humanReviewRecommended", False),
        "sections": {
            "overview": {
                "title": "Overview",
                "body": triage.get("reasoningSummary") or "",
            },
            "rights": {
                "title": "Your options",
                "items": [
                    {
                        "title": "Review support first",
                        "body": (
                            "SafeSpeak can help you review support, evidence, and reporting "
                            "steps without sending anything automatically."
                        ),
                    }
                ],
            },
            "reportingOptions": {"title": "Reporting options", "items": recommendations},
            "evidenceGuide": {
                "title": "Evidence guide",
                "items": [{"title": "Keep only what feels necessary", "facts": serialized_facts}],
            },
            "supportServices": {"title": "Support services", "items": recommendations},
            "safetyPlanning": {
                "title": "Safety planning",
                "items": [{"title": "Focus on immediate safety first when risk feels urgent."}],
            },
        },
        "disclaimer": "This is information only, not legal advice.",
    }


async def create_conversation_flow_session(
    context: dict[str, Any],
    input_data: CreateConversationFlowSessionInput,
    *,
    repository: ConversationFlowRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_conversation_flow_repository()
    await _require_storage_consent(context["owner"])
    created = await repository.create_session(
        {
            **_owner_filter(context["owner"]),
            "selectedTopic": input_data.selected_topic,
            "jurisdiction": input_data.jurisdiction,
            "location": input_data.location,
            "status": "active",
            "safetyRiskLevel": "low",
            "latestTurnRiskLevel": "none",
            "activeIncidentRiskLevel": "none",
            "sessionHistoricalMaxRiskLevel": "none",
            "assistantFormatPreference": "paragraphs",
            "messageCount": 0,
            "userTurnCount": 0,
        }
    )
    await _audit(
        context,
        CONVERSATION_FLOW_ACTIONS["sessionCreate"],
        str(created["_id"]),
        metadata={
            "selectedTopic": input_data.selected_topic,
            "jurisdiction": input_data.jurisdiction,
        },
    )
    return {"session": _session_record(created)}


async def get_conversation_flow_session(
    context: dict[str, Any],
    conversation_session_id: str,
    *,
    repository: ConversationFlowRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_conversation_flow_repository()
    session = await _get_owned_session(context, conversation_session_id, repository=repository)
    messages = await repository.list_messages(conversation_session_id)
    facts = await repository.get_facts(conversation_session_id)
    triage = await repository.get_triage(conversation_session_id)
    await _audit(context, CONVERSATION_FLOW_ACTIONS["sessionGet"], conversation_session_id)
    return {
        "session": _session_record(session),
        "messages": [_message_record(item) for item in messages],
        "factExtraction": _facts_record(facts),
        "triage": _triage_record(triage),
    }


async def append_conversation_flow_message(
    context: dict[str, Any],
    conversation_session_id: str,
    input_data: AppendConversationFlowMessageInput,
    *,
    repository: ConversationFlowRepository | None = None,
    assistant: ConversationAssistantPort | None = None,
) -> dict[str, Any]:
    repository = repository or get_conversation_flow_repository()
    assistant = assistant or get_conversation_assistant()
    consent = await _require_storage_consent(context["owner"])
    session = await _get_owned_session(context, conversation_session_id, repository=repository)
    existing_messages = await repository.list_messages(conversation_session_id)
    next_user_turn = session.get("messageCount", 0) + 1
    next_assistant_turn = next_user_turn + 1

    user_message = await repository.create_message(
        {
            "conversationSessionId": ObjectId(conversation_session_id),
            "role": "user",
            "content": input_data.content,
            "turnNumber": next_user_turn,
            "metadata": {},
        }
    )
    session = (
        await repository.update_session(
            conversation_session_id,
            context["owner"],
            {
                "messageCount": next_assistant_turn,
                "userTurnCount": session.get("userTurnCount", 0) + 1,
                "detectedLanguage": input_data.language,
            },
        )
        or session
    )

    assistant_payload = await assistant.respond(
        session=session,
        messages=[*existing_messages, user_message],
        latest_user_message=input_data.content,
        language=input_data.language,
        consent=consent,
    )
    assistant_message = await repository.create_message(
        {
            "conversationSessionId": ObjectId(conversation_session_id),
            "role": "assistant",
            "content": " ".join(
                part
                for part in (
                    assistant_payload.get("assistantMessage"),
                    assistant_payload.get("nextQuestion"),
                )
                if part
            ),
            "turnNumber": next_assistant_turn,
            "metadata": assistant_payload,
        }
    )

    existing_facts = await repository.get_facts(conversation_session_id)
    merged_timeline = _merge_timeline(
        dict((existing_facts or {}).get("timeline") or {}),
        extract_timeline(input_data.content),
    )
    facts_payload = _facts_from_timeline(merged_timeline)
    facts_payload["missingInformation"] = build_missing_information(facts_payload)
    facts = await repository.upsert_facts(conversation_session_id, facts_payload)
    all_messages = [*existing_messages, user_message, assistant_message]
    triage = await _build_triage(session, all_messages, facts, repository=repository)
    offer_triage = can_offer_triage(
        session.get("userTurnCount", 0),
        facts_payload,
        triage.get("confidenceScore", 0),
    ) or (
        session.get("userTurnCount", 0) >= 1
        and (triage.get("likelyCategory") or "general_support") != "general_support"
    )
    session_updates: dict[str, Any] = {
        "latestTurnRiskLevel": (
            assistant_payload.get("latestTurnRiskLevel") or triage.get("safetyRiskLevel")
        ),
        "activeIncidentRiskLevel": triage.get("safetyRiskLevel"),
        "sessionHistoricalMaxRiskLevel": triage.get("safetyRiskLevel"),
        "status": "ready_for_triage" if offer_triage else session.get("status", "active"),
    }
    if offer_triage and not session.get("triageOfferedAt"):
        session_updates["triageOfferedAt"] = datetime.now(UTC)
    session = (
        await repository.update_session(conversation_session_id, context["owner"], session_updates)
        or session
    )
    await _audit(
        context,
        CONVERSATION_FLOW_ACTIONS["messageAppend"],
        conversation_session_id,
        metadata={
            "offeredTriage": offer_triage,
            "detectedCategory": triage.get("likelyCategory"),
        },
    )
    response = {
        "session": _session_record(session),
        "userMessage": _message_record(user_message),
        "assistantMessage": _message_record(assistant_message),
        "factExtraction": _facts_record(facts),
        "triage": _triage_record(triage),
        "transition": {
            "offerTriage": offer_triage,
            "prompt": None,
            "primaryCta": "Continue to Triage" if offer_triage else None,
            "secondaryCta": "Review options" if offer_triage else None,
        },
        "responseMeta": {
            "confidence": assistant_payload.get("confidence"),
            "disclaimer": assistant_payload.get("disclaimer"),
            "intent": assistant_payload.get("intent"),
            "triageReady": offer_triage,
            "nextAction": "triage" if offer_triage else "continue_conversation",
            "conversationSessionId": conversation_session_id,
            "selectedResponseSource": assistant_payload.get("selectedResponseSource"),
            "responseSource": assistant_payload.get("responseSource"),
            "ragStatus": "not_required",
            "showSources": assistant_payload.get("showSources", False),
            "reviewStatus": assistant_payload.get("reviewStatus"),
            "assistantLanguage": assistant_payload.get("assistantLanguage"),
            "triageUpdated": assistant_payload.get("triageUpdated", True),
            "latestTurnRiskLevel": session.get("latestTurnRiskLevel"),
            "activeIncidentRiskLevel": session.get("activeIncidentRiskLevel"),
            "sessionHistoricalMaxRiskLevel": session.get("sessionHistoricalMaxRiskLevel"),
            "assistantFormatPreference": session.get("assistantFormatPreference"),
            "formatPreferenceUpdated": False,
        },
    }
    if input_data.debug_response == "minimal":
        return {
            "session": response["session"],
            "assistantMessage": response["assistantMessage"],
            "transition": response["transition"],
            "responseMeta": response["responseMeta"],
        }
    return response


async def get_conversation_flow_triage(
    context: dict[str, Any],
    conversation_session_id: str,
    *,
    repository: ConversationFlowRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_conversation_flow_repository()
    session = await _get_owned_session(context, conversation_session_id, repository=repository)
    messages = await repository.list_messages(conversation_session_id)
    facts = await repository.get_facts(conversation_session_id)
    triage = await _build_triage(
        session, messages, facts, repository=repository, finalize_session=True
    )
    session = await _get_owned_session(context, conversation_session_id, repository=repository)
    await _audit(
        context,
        CONVERSATION_FLOW_ACTIONS["triageGet"],
        conversation_session_id,
        metadata={"likelyCategory": triage.get("likelyCategory")},
    )
    return {"session": _session_record(session), "triage": _triage_record(triage)}


async def get_conversation_flow_support(
    context: dict[str, Any],
    conversation_session_id: str,
    *,
    repository: ConversationFlowRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_conversation_flow_repository()
    session = await _get_owned_session(context, conversation_session_id, repository=repository)
    messages = await repository.list_messages(conversation_session_id)
    facts = await repository.get_facts(conversation_session_id)
    triage = await _build_triage(
        session, messages, facts, repository=repository, finalize_session=True
    )
    await _audit(
        context,
        CONVERSATION_FLOW_ACTIONS["supportGet"],
        conversation_session_id,
        metadata={"likelyCategory": triage.get("likelyCategory")},
    )
    return {
        "session": _session_record(
            await _get_owned_session(context, conversation_session_id, repository=repository)
        ),
        "triage": _triage_record(triage),
        "support": _support_bundle(session, triage, facts),
    }


async def get_conversation_flow_recommendations(
    context: dict[str, Any],
    conversation_session_id: str,
    *,
    repository: ConversationFlowRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_conversation_flow_repository()
    session = await _get_owned_session(context, conversation_session_id, repository=repository)
    triage = await repository.get_triage(conversation_session_id)
    if not triage:
        messages = await repository.list_messages(conversation_session_id)
        facts = await repository.get_facts(conversation_session_id)
        triage = await _build_triage(session, messages, facts, repository=repository)
    recommendations = _recommendations_for_triage(triage, session.get("jurisdiction"))
    if triage.get("canProceedToRecommendations"):
        session = (
            await repository.update_session(
                conversation_session_id, context["owner"], {"status": "recommendation_ready"}
            )
            or session
        )
    await _audit(
        context,
        CONVERSATION_FLOW_ACTIONS["recommendationsGet"],
        conversation_session_id,
        metadata={"count": len(recommendations)},
    )
    return {
        "session": _session_record(session),
        "recommendations": recommendations,
        "fallbackUsed": True,
    }


async def get_conversation_flow_details(
    context: dict[str, Any],
    conversation_session_id: str,
    *,
    repository: ConversationFlowRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_conversation_flow_repository()
    session = await _get_owned_session(context, conversation_session_id, repository=repository)
    triage = await repository.get_triage(conversation_session_id)
    if not triage:
        messages = await repository.list_messages(conversation_session_id)
        facts = await repository.get_facts(conversation_session_id)
        triage = await _build_triage(session, messages, facts, repository=repository)
    facts = await repository.get_facts(conversation_session_id)
    recommendations = _recommendations_for_triage(triage, session.get("jurisdiction"))
    await _audit(context, CONVERSATION_FLOW_ACTIONS["detailsGet"], conversation_session_id)
    return {
        "session": _session_record(session),
        "details": _details_payload(triage, recommendations, facts),
    }
