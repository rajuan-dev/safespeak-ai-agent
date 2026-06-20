import re
from typing import Any

from app.core.config import get_settings
from app.services.llm import llm_service

WORD_RE = re.compile(r"[A-Za-z0-9]{2,}")
EXPLICIT_SECTION_RE = re.compile(
    r"\b(?:section|sections|s)\.?\s*([0-9]{1,4}[A-Za-z]?(?:\([0-9A-Za-z]+\))*)",
    re.I,
)
HISTORICAL_QUERY_RE = re.compile(
    r"\b(historical|previous version|former|before amendment|at the time|as at|repealed)\b",
    re.I,
)


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in WORD_RE.findall(text)}


def _deterministic_score(query: str, result: dict[str, Any], rank: int) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(
        " ".join(
            str(value or "")
            for value in (
                result.get("title"),
                result.get("sectionRef"),
                result.get("sectionTitle"),
                result.get("text"),
            )
        )
    )
    overlap = len(query_tokens & text_tokens) / max(1, len(query_tokens))
    score = overlap * 4 + 1 / (rank + 1)
    explicit_sections = {value.casefold() for value in EXPLICIT_SECTION_RE.findall(query)}
    section_ref = str(result.get("sectionRef") or "").casefold()
    section_number = section_ref.split("(")[0]
    if section_ref in explicit_sections:
        score += 10
    elif section_number and any(value.startswith(section_number) for value in explicit_sections):
        score += 5
    if str(result.get("title") or "").casefold() in query.casefold():
        score += 3
    if (
        (result.get("metadata") or {}).get("amendmentStatus") == "repealed"
        and not HISTORICAL_QUERY_RE.search(query)
    ):
        score -= 6
    return score


def deterministic_rerank(
    query: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deterministic = sorted(
        enumerate(results),
        key=lambda item: _deterministic_score(query, item[1], item[0]),
        reverse=True,
    )
    return [item[1] for item in deterministic]


async def rerank_results(
    query: str,
    results: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    if not results:
        return []
    ordered = deterministic_rerank(query, results)
    settings = get_settings()
    if (
        settings.RAG_RERANK_PROVIDER not in {"openai", "hybrid"}
        or not settings.OPENAI_API_KEY
        or len(ordered) < 2
    ):
        return ordered[:top_k]

    candidates = [
        {
            "chunkId": item.get("chunkId"),
            "title": item.get("title"),
            "sectionRef": item.get("sectionRef"),
            "sectionTitle": item.get("sectionTitle"),
            "text": str(item.get("text") or "")[:1800],
        }
        for item in ordered[: settings.RAG_RERANK_CANDIDATES]
    ]
    response = await llm_service.json_completion(
        system=(
            "Score legal retrieval candidates for direct relevance to the question. "
            "Do not answer the question. Exact requested provisions and governing definitions "
            "must rank above general mentions. Return JSON: "
            '{"ranking":[{"chunkId":"...","score":0.0,"reason":"..."}]}.'
        ),
        user=f"Question: {query}\nCandidates: {candidates}",
        fallback={"ranking": []},
    )
    ranking = response.get("ranking")
    if not isinstance(ranking, list):
        return ordered[:top_k]
    model_order = {
        str(item.get("chunkId")): float(item.get("score", 0))
        for item in ranking
        if isinstance(item, dict) and item.get("chunkId")
    }
    if not model_order:
        return ordered[:top_k]
    deterministic_position = {
        str(item.get("chunkId")): position for position, item in enumerate(ordered)
    }
    ordered.sort(
        key=lambda item: (
            model_order.get(str(item.get("chunkId")), -1),
            -deterministic_position.get(str(item.get("chunkId")), 10_000),
        ),
        reverse=True,
    )
    return ordered[:top_k]
