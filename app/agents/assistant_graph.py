from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.common import SearchInput, TimelineAssistantInput
from app.services.llm import llm_service
from app.services.retrieval import hybrid_search


class AssistantState(TypedDict, total=False):
    request: TimelineAssistantInput
    results: list[dict[str, Any]]
    output: dict[str, Any]


async def retrieve_support(state: AssistantState) -> AssistantState:
    request = state["request"]
    legal_intent = any(
        term in request.message.lower()
        for term in ("law", "legal", "act", "section", "rights", "offence", "report")
    )
    if not legal_intent:
        return {"results": []}
    search = SearchInput(
        query=request.message,
        topK=request.topK,
        jurisdiction=request.jurisdiction,
        sourceCategory="official_legal_source",
    )
    return {"results": await hybrid_search(search)}


async def build_turn(state: AssistantState) -> AssistantState:
    request = state["request"]
    results = state.get("results", [])
    context = "\n\n".join(item["text"] for item in results)
    generated = await llm_service.json_completion(
        system=(
            "You are a trauma-informed SafeSpeak assistant helping a user build an incident "
            "timeline. Do not diagnose or give legal advice. Ask at most one gentle next question. "
            "Never pressure the user for identifying details. Preserve existing timeline values. "
            "If legal context is supplied, use only that context. Return JSON with "
            "assistantMessage, nextQuestion, timeline, readyForSubmission, confidence."
        ),
        user=(
            f"Latest message: {request.message}\n"
            f"Existing timeline: {request.timeline}\n"
            f"Recent conversation: {[item.model_dump() for item in request.conversation[-8:]]}\n"
            f"Optional approved context: {context}"
        ),
        fallback={
            "assistantMessage": (
                "I have added what you shared. What date or approximate time did this happen?"
            ),
            "nextQuestion": "What date or approximate time did this happen?",
            "timeline": request.timeline,
            "readyForSubmission": False,
            "confidence": "low",
        },
    )
    timeline = generated.get("timeline")
    if not isinstance(timeline, dict):
        timeline = request.timeline
    citations = [
        {
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
        for item in results
    ]
    return {
        "output": {
            "assistantMessage": generated.get("assistantMessage", ""),
            "nextQuestion": generated.get("nextQuestion", ""),
            "timeline": timeline,
            "readyForSubmission": bool(generated.get("readyForSubmission", False)),
            "confidence": generated.get("confidence", "medium"),
            "disclaimer": "SafeSpeak provides information and support, not legal advice.",
            "citations": citations,
            "showSources": bool(citations),
            "sourceDisplayReason": "legal_lookup" if citations else "hidden_support_reply",
            "rag": {
                "used": bool(citations),
                "unavailable": False,
                "resultCount": len(citations),
            },
            "reviewStatus": "generated",
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
