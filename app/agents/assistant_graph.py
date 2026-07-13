import asyncio
from typing import Any, TypedDict

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.models.common import SearchInput, TimelineAssistantInput
from app.services.backend_ai import (
    INFORMATION_ONLY_DISCLAIMER,
    build_response_plan,
    build_turn_policy,
    classify_intent,
    response_mode_for_intent,
    split_guardrail_violations,
    validate_response,
)
from app.services.legal_readiness import assert_legal_runtime_ready
from app.services.llm import llm_service
from app.services.retrieval import hybrid_search
from app.services.source_templates import build_template_prompt_block, resolve_source_templates

TIMELINE_KEYS = {
    "who",
    "relationship",
    "what",
    "where",
    "when",
    "how",
    "frequency",
    "impact",
    "threats",
    "injuries",
    "witnesses",
    "evidence",
    "actions_taken",
    "unsafe_now",
}


class AssistantState(TypedDict, total=False):
    request: TimelineAssistantInput
    results: list[dict[str, Any]]
    rag_unavailable: bool
    output: dict[str, Any]


async def retrieve_support(state: AssistantState) -> AssistantState:
    request = state["request"]
    classification = classify_intent(request.message)
    response_mode = response_mode_for_intent(classification["intent"])
    turn_policy = build_turn_policy(classification["intent"], request.message, response_mode)
    if not turn_policy["ragRequired"]:
        return {"results": [], "rag_unavailable": False}
    try:
        assert_legal_runtime_ready()
        legal_search = SearchInput(
            query=request.message,
            topK=request.topK,
            jurisdiction=request.jurisdiction,
            sourceCategory="official_legal_source",
        )
        support_search = SearchInput(
            query=request.message,
            topK=request.topK,
            jurisdiction=request.jurisdiction,
            sourceCategory="official_support_source",
        )
        legal_results, support_results = await asyncio.gather(
            hybrid_search(legal_search),
            hybrid_search(support_search),
        )
        combined: list[dict[str, Any]] = []
        seen_chunk_ids: set[str] = set()
        for item in [*legal_results, *support_results]:
            chunk_id = str(item.get("chunkId") or "")
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            combined.append(item)
            if len(combined) >= request.topK:
                break
        return {"results": combined, "rag_unavailable": False}
    except HTTPException:
        return {"results": [], "rag_unavailable": True}


def _citation_from_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceId": item.get("sourceId"),
        "title": item.get("title"),
        "publisher": item.get("publisher"),
        "url": item.get("citationUrl"),
        "jurisdiction": item.get("jurisdiction"),
        "sourceCategory": item.get("sourceCategory"),
        "sourceType": item.get("sourceType"),
        "topic": item.get("topic"),
        "sectionRef": item.get("sectionRef"),
        "sectionTitle": item.get("sectionTitle"),
        "page": item.get("pageNumber"),
        "pageStart": (item.get("metadata") or {}).get("pageStart"),
        "pageEnd": (item.get("metadata") or {}).get("pageEnd"),
        "versionDate": item.get("versionDate"),
        "commencementDate": item.get("commencementDate"),
        "amendmentStatus": item.get("amendmentStatus"),
        "lastUpdated": item.get("lastUpdated"),
    }


def _clean_timeline(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    cleaned_fallback: dict[str, Any] = {}
    for key, raw_value in fallback.items():
        if not isinstance(key, str) or key not in TIMELINE_KEYS or raw_value is None:
            continue
        text = str(raw_value).strip()
        if text:
            cleaned_fallback[key] = text[:240]

    if not isinstance(value, dict):
        return cleaned_fallback

    cleaned: dict[str, Any] = {}
    for key, raw_value in value.items():
        if not isinstance(key, str) or key not in TIMELINE_KEYS:
            continue
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if text:
            cleaned[key] = text[:240]
    return {**cleaned_fallback, **cleaned}


def _one_question(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    question = " ".join(value.split())
    if not question:
        return ""
    return question[:240]


def _confidence(value: Any) -> str:
    return value if value in {"low", "medium", "high"} else "medium"


def _visible_reply_text(assistant_message: str, next_question: str) -> str:
    trimmed_assistant_message = assistant_message.strip()
    trimmed_next_question = next_question.strip()
    if not trimmed_assistant_message:
        return trimmed_next_question
    if not trimmed_next_question:
        return trimmed_assistant_message
    if trimmed_assistant_message.lower() == trimmed_next_question.lower():
        return trimmed_assistant_message
    return f"{trimmed_assistant_message} {trimmed_next_question}"


async def build_turn(state: AssistantState) -> AssistantState:
    request = state["request"]
    results = state.get("results", [])
    rag_unavailable = bool(state.get("rag_unavailable", False))
    classification = classify_intent(request.message)
    intent = classification["intent"]
    response_mode = response_mode_for_intent(intent)
    turn_policy = build_turn_policy(intent, request.message, response_mode)
    response_plan = build_response_plan(intent, request.message, turn_policy)
    context = "\n\n".join(item["text"] for item in results)
    citations = [_citation_from_result(item) for item in results]
    resolved_templates = resolve_source_templates(results)
    template_prompt_block = build_template_prompt_block(resolved_templates)
    rag_status = (
        "retrieved"
        if citations
        else "required_but_no_sources_found"
        if turn_policy["ragRequired"]
        else "not_required"
    )
    review_status = (
        "generated_with_rag_unavailable"
        if rag_unavailable
        else "generated"
    )
    response_source = "openai_model_with_rag" if citations else "openai_model"
    generated = await llm_service.json_completion(
        system=(
            "You are SafeSpeak Guide, a multilingual, trauma-informed community safety "
            "and support navigation guide for Australia. You are not a lawyer, police "
            "officer, therapist, counsellor, emergency service, or case manager. Follow "
            "the backend SafeSpeak principles exactly: human first, triage before data "
            "collection, minimum necessary information, understand not decide, pathways "
            "over laws, and authoritative RAG only. Do not diagnose, decide legal status, "
            "or give legal, clinical, counselling, crisis-service, or case-management "
            "advice. Ask at most one user-facing question unless emergency safety requires "
            "otherwise. Do not pressure the user for identifying details. Preserve existing "
            "timeline values. If legal or pathway context is supplied, use only that context "
            "and do not invent citations. If source-specific response templates are provided, "
            "treat them as style guidance only and never as facts. Return valid JSON with keys: assistantMessage, "
            "nextQuestion, timeline, readyForSubmission, confidence, citations, reviewStatus."
        ),
        user=(
            f"Intent classification: {classification}\n"
            f"Response mode: {response_mode}\n"
            f"Turn policy: {turn_policy}\n"
            f"Response plan: {response_plan}\n"
            f"Latest message: {request.message}\n"
            f"Existing timeline: {request.timeline}\n"
            f"Recent conversation: {[item.model_dump() for item in request.conversation[-8:]]}\n"
            f"Quick-start category: {request.incidentCategory or 'none'}\n"
            f"Language: {request.language or 'en'}\n"
            f"Jurisdiction: {request.jurisdiction or 'unknown'}\n"
            f"RAG status: {rag_status}\n"
            f"Source template guidance: {template_prompt_block}\n"
            f"Optional approved context: {context or 'No approved RAG context was retrieved.'}"
        ),
        fallback={
            "assistantMessage": (
                "I have added what you shared. What date or approximate time did this happen?"
            ),
            "nextQuestion": "What date or approximate time did this happen?",
            "timeline": request.timeline,
            "readyForSubmission": False,
            "confidence": "low",
            "citations": [],
            "reviewStatus": review_status,
        },
    )
    timeline = _clean_timeline(generated.get("timeline"), request.timeline)
    assistant_message = str(generated.get("assistantMessage") or "").strip()
    if not assistant_message:
        assistant_message = "I can help you take this one step at a time."
        response_source = "model_empty_fallback"
    next_question = _one_question(generated.get("nextQuestion"))
    if not response_plan["questionAllowed"]:
        next_question = ""

    validation = validate_response(
        text=_visible_reply_text(assistant_message, next_question),
        intent=intent,
        latest_user_message=request.message,
        response_plan=response_plan,
    )
    violations = split_guardrail_violations(validation["violations"])
    guardrail_status = "passed"
    fallback_reason = None
    if violations["hard"]:
        guardrail_status = "fallback"
        fallback_reason = ",".join(violations["hard"])
        response_source = "guardrail_fallback"
        assistant_message = (
            "If you are in immediate danger in Australia, call 000 now."
            if intent == "safety_crisis"
            else "I'm sorry, I couldn't generate a reliable response just now. Please try again."
        )
        next_question = ""
    elif violations["soft"]:
        if "too_many_questions" in violations["soft"] and next_question:
            next_question = ""
            validation = validate_response(
                text=_visible_reply_text(assistant_message, next_question),
                intent=intent,
                latest_user_message=request.message,
                response_plan=response_plan,
            )
            violations = split_guardrail_violations(validation["violations"])
        if violations["hard"]:
            guardrail_status = "fallback"
            fallback_reason = ",".join(violations["hard"])
            response_source = "guardrail_fallback"
            assistant_message = (
                "If you are in immediate danger in Australia, call 000 now."
                if intent == "safety_crisis"
                else "I'm sorry, I couldn't generate a reliable response just now. Please try again."
            )
            next_question = ""
        elif violations["soft"]:
            guardrail_status = "flagged"
            fallback_reason = ",".join(violations["soft"])
    source_display_reason = (
        "legal_lookup"
        if citations and turn_policy["sourcesVisible"]
        else "not_directly_grounded"
        if turn_policy["ragRequired"] and not citations
        else "hidden_support_reply"
    )
    return {
        "output": {
            "assistantMessage": assistant_message,
            "nextQuestion": next_question,
            "timeline": timeline,
            "readyForSubmission": bool(generated.get("readyForSubmission", False)),
            "confidence": _confidence(generated.get("confidence")),
            "disclaimer": resolved_templates.get("disclaimer") or INFORMATION_ONLY_DISCLAIMER,
            "citations": citations,
            "showSources": bool(citations and turn_policy["sourcesVisible"]),
            "sourceDisplayReason": source_display_reason,
            "rag": {
                "used": bool(citations),
                "unavailable": rag_unavailable,
                "resultCount": len(citations),
            },
            "reviewStatus": str(generated.get("reviewStatus") or review_status),
            "responseMode": "safespeak_model",
            "intent": intent,
            "intentConfidence": classification["confidence"],
            "classifierSource": classification["classifierSource"],
            "matchedSignals": classification["matchedSignals"],
            "usedModelGeneration": bool(llm_service.client),
            "guardrailStatus": guardrail_status,
            "fallbackReason": fallback_reason,
            "staticTemplateUsed": not bool(llm_service.client),
            "responseSource": response_source,
            "selectedResponseSource": response_source,
            "model": get_settings().OPENAI_MODEL,
            "jurisdiction": "AU",
            "ragStatus": rag_status,
            "sourceTemplatesApplied": bool(resolved_templates.get("used")),
            "sourceTemplateSourceId": resolved_templates.get("selectedSourceId"),
            "sourceTemplateSourceTitle": resolved_templates.get("selectedSourceTitle"),
            "responsePlan": response_plan,
            "turnPolicyDecision": turn_policy,
            "responseStrategy": turn_policy["responseStrategy"],
            "groundedAnswerRequired": turn_policy["groundedAnswerRequired"],
            "disclaimerRequired": turn_policy["disclaimerRequired"],
            "assistantLanguage": request.language or "en",
            "nonIncidentTurn": not turn_policy["timelineCollectionAllowed"],
            "triageUpdated": intent
            in {
                "safety_crisis",
                "physical_harm",
                "incident_disclosure",
                "scam_check",
                "rag_pathway_question",
            },
            "humanReviewRecommended": bool(
                turn_policy["humanReviewRecommended"] or citations or rag_unavailable
            ),
            "humanReviewReasons": list(
                dict.fromkeys(
                    turn_policy["humanReviewReasons"]
                    + (
                        ["may_influence_legal_or_reporting_decision"]
                        if citations or rag_unavailable
                        else []
                    )
                )
            ),
        }
    }


builder = StateGraph(AssistantState)
builder.add_node("retrieve_support", retrieve_support)
builder.add_node("build_turn", build_turn)
builder.add_edge(START, "retrieve_support")
builder.add_edge("retrieve_support", "build_turn")
builder.add_edge("build_turn", END)
assistant_graph = builder.compile()


async def run_timeline_assistant(request: TimelineAssistantInput) -> dict[str, Any]:
    state = await assistant_graph.ainvoke({"request": request})
    return state["output"]
