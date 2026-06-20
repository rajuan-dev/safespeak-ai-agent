import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.common import AnswerInput, SearchInput
from app.services.citation_verifier import verify_grounded_answer
from app.services.llm import llm_service
from app.services.retrieval import hybrid_search

DISCLAIMER = (
    "This is general legal information from the cited sources, not legal advice. "
    "Check the current official legislation and seek qualified advice for your situation."
)


class RagState(TypedDict, total=False):
    request: AnswerInput
    results: list[dict[str, Any]]
    output: dict[str, Any]


def _citation(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceId": result.get("sourceId"),
        "title": result.get("title"),
        "publisher": result.get("publisher"),
        "sourceAuthority": result.get("sourceAuthority"),
        "url": result.get("citationUrl"),
        "jurisdiction": result.get("jurisdiction"),
        "sourceCategory": result.get("sourceCategory"),
        "sourceType": result.get("sourceType"),
        "topic": result.get("topic"),
        "sectionRef": result.get("sectionRef"),
        "sectionTitle": result.get("sectionTitle"),
        "page": result.get("pageNumber"),
        "pageStart": (result.get("metadata") or {}).get("pageStart"),
        "pageEnd": (result.get("metadata") or {}).get("pageEnd"),
        "versionDate": result.get("versionDate"),
        "commencementDate": result.get("commencementDate"),
        "amendmentStatus": result.get("amendmentStatus"),
        "amendingInstrument": result.get("amendingInstrument"),
        "relatedProvisions": result.get("crossReferences"),
        "lastUpdated": result.get("lastUpdated"),
    }


async def retrieve(state: RagState) -> RagState:
    request = state["request"]
    search = SearchInput.model_validate(
        {**request.model_dump(exclude={"question"}), "query": request.question}
    )
    return {"results": await hybrid_search(search)}


async def generate(state: RagState) -> RagState:
    request = state["request"]
    results = state.get("results", [])
    if not results:
        return {
            "output": {
                "answer": "The information was not found in the available approved legal data.",
                "disclaimer": DISCLAIMER,
                "citations": [],
                "sourceCategoriesUsed": [],
                "confidence": "low",
                "pendingHumanReview": True,
                "safetyFlags": {"insufficientSources": True},
            }
        }

    context = "\n\n".join(
        (
            f"[SOURCE {index}]\n"
            f"Act/source: {item.get('title')}\n"
            f"Section: {item.get('sectionRef') or 'not stated'}\n"
            f"Page: {item.get('pageNumber') or 'not stated'}\n"
            f"Version date: {item.get('versionDate') or 'not stated'}\n"
            f"Commencement date: {item.get('commencementDate') or 'not stated'}\n"
            f"Provision status: {item.get('amendmentStatus') or 'not stated'}\n"
            f"Hierarchy: {(item.get('metadata') or {}).get('hierarchyPath') or []}\n"
            f"Resolved related provisions: {item.get('crossReferences') or []}\n"
            f"Text:\n{item.get('text')}"
        )
        for index, item in enumerate(results, start=1)
    )
    generated = await llm_service.json_completion(
        system=(
            "You are SafeSpeak's Australian legal information assistant. Answer only from the "
            "provided source text. Preserve legal qualifications and defined terms. Never invent "
            "a section, date, penalty, exception, or legal conclusion. If the sources do not "
            "contain the answer, say exactly that it was not found in the available legal data. "
            "Return JSON with keys answer and confidence. Use plain language but do not alter the "
            "legal meaning. Every factual or legal sentence must end with one or more markers such "
            "as [SOURCE 1]. Do not cite a source that does not directly support that sentence."
        ),
        user=f"Question:\n{request.question}\n\nApproved legal sources:\n{context}",
        fallback={
            "answer": "The information was not found in the available approved legal data.",
            "confidence": "low",
        },
    )
    answer = str(generated.get("answer", "")).strip()
    if re.search(r"\bnot found in the available (?:approved )?legal data\b", answer, re.I):
        return {
            "output": {
                "answer": "The information was not found in the available approved legal data.",
                "disclaimer": DISCLAIMER,
                "citations": [],
                "sourceCategoriesUsed": [],
                "confidence": "low",
                "pendingHumanReview": True,
                "safetyFlags": {"insufficientSources": True},
            }
        }
    verification = verify_grounded_answer(answer, results)
    if not verification.supported:
        return {
            "output": {
                "answer": "The information was not found in the available approved legal data.",
                "disclaimer": DISCLAIMER,
                "citations": [],
                "sourceCategoriesUsed": [],
                "confidence": "low",
                "pendingHumanReview": True,
                "safetyFlags": {
                    "insufficientSources": True,
                    "citationGate": "failed",
                    "citationErrors": verification.errors,
                },
            }
        }

    return {
        "output": {
            "answer": answer,
            "disclaimer": DISCLAIMER,
            "citations": [_citation(result) for result in results],
            "sourceCategoriesUsed": sorted(
                {str(result.get("sourceCategory")) for result in results}
            ),
            "confidence": generated.get("confidence", "medium"),
            "pendingHumanReview": False,
            "safetyFlags": {
                "insufficientSources": False,
                "citationGate": "passed",
                "supportedSentences": verification.supported_sentences,
                "totalSentences": verification.total_sentences,
            },
        }
    }


builder = StateGraph(RagState)
builder.add_node("retrieve", retrieve)
builder.add_node("generate", generate)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", END)
rag_graph = builder.compile()


async def answer_question(request: AnswerInput) -> dict[str, Any]:
    state = await rag_graph.ainvoke({"request": request})
    return state["output"]
