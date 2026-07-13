import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.common import AnswerInput, SearchInput
from app.services.citation_verifier import verify_grounded_answer
from app.services.llm import llm_service
from app.services.retrieval import hybrid_search
from app.services.source_templates import (
    DEFAULT_RAG_DISCLAIMER,
    build_template_prompt_block,
    resolve_source_templates,
)


class RagState(TypedDict, total=False):
    request: AnswerInput
    results: list[dict[str, Any]]
    output: dict[str, Any]


def _result_categories(results: list[dict[str, Any]]) -> set[str]:
    return {str(result.get("sourceCategory") or "") for result in results}


def _source_data_label(results: list[dict[str, Any]]) -> str:
    categories = _result_categories(results)
    if categories and categories <= {"official_support_source"}:
        return "approved support source data"
    if "official_support_source" in categories:
        return "approved source data"
    return "approved legal data"


def _not_found_message(results: list[dict[str, Any]]) -> str:
    return f"The information was not found in the available {_source_data_label(results)}."


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


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for citation in citations:
        key = (
            str(citation.get("sourceId") or ""),
            str(citation.get("sectionRef") or ""),
            str(citation.get("page") or citation.get("pageStart") or ""),
            str(citation.get("url") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


async def retrieve(state: RagState) -> RagState:
    request = state["request"]
    search = SearchInput.model_validate(
        {**request.model_dump(exclude={"question"}), "query": request.question}
    )
    return {"results": await hybrid_search(search)}


async def generate(state: RagState) -> RagState:
    request = state["request"]
    results = state.get("results", [])
    resolved_templates = resolve_source_templates(results)
    if not results:
        return {
            "output": {
                "answer": _not_found_message(results),
                "disclaimer": DEFAULT_RAG_DISCLAIMER,
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
    template_prompt_block = build_template_prompt_block(resolved_templates)
    source_data_label = _source_data_label(results)
    not_found_message = _not_found_message(results)
    generated = await llm_service.json_completion(
        system=(
            "You are SafeSpeak's grounded source assistant for Australian legal and support "
            "information. Answer only from the provided source text. Preserve qualifications, "
            "definitions, and source meaning. Never invent a section, date, penalty, exception, "
            "support service rule, or legal conclusion. If the sources do not contain the answer, "
            f"say exactly: {not_found_message} Return JSON with keys answer and confidence. Use "
            "plain language but do not alter the source meaning. Every factual sentence must end "
            "with one or more markers such as [SOURCE 1]. Do not cite a source that does not "
            "directly support that sentence. If source-specific response templates are provided, "
            "treat them as wording guidance only and never as evidence."
        ),
        user=(
            f"Question:\n{request.question}\n\n"
            f"Source data type:\n{source_data_label}\n\n"
            f"Source template guidance:\n{template_prompt_block}\n\n"
            f"Approved sources:\n{context}"
        ),
        fallback={
            "answer": not_found_message,
            "confidence": "low",
        },
    )
    answer = str(generated.get("answer", "")).strip()
    if re.search(r"\bnot found in the available (?:approved )?(?:legal|support|source) data\b", answer, re.I):
        return {
            "output": {
                "answer": not_found_message,
                "disclaimer": DEFAULT_RAG_DISCLAIMER,
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
                "answer": not_found_message,
                "disclaimer": DEFAULT_RAG_DISCLAIMER,
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

    citations = _dedupe_citations([_citation(result) for result in results])

    return {
        "output": {
            "answer": answer,
            "disclaimer": resolved_templates.get("disclaimerPhrasing") or DEFAULT_RAG_DISCLAIMER,
            "citations": citations,
            "sourceCategoriesUsed": sorted(
                {str(result.get("sourceCategory")) for result in results}
            ),
            "confidence": generated.get("confidence", "medium"),
            "pendingHumanReview": False,
            "sourceTemplatesApplied": bool(resolved_templates.get("used")),
            "sourceTemplateSourceId": resolved_templates.get("selectedSourceId"),
            "sourceTemplateSourceTitle": resolved_templates.get("selectedSourceTitle"),
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
