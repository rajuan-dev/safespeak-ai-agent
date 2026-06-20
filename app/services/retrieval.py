import re
from collections import defaultdict
from typing import Any

from bson import ObjectId
from pymongo.errors import OperationFailure

from app.core.config import get_settings
from app.core.database import get_database
from app.models.common import SearchInput
from app.services.embeddings import embedding_service
from app.services.knowledge import CHUNK_COLLECTION, SOURCE_COLLECTION
from app.services.reranking import rerank_results
from app.services.serialization import json_safe
from app.services.vector_store import pinecone_store

SECTION_QUERY_RE = re.compile(
    r"\b(?:section|sections|s)\.?\s*([0-9]{1,4}[A-Za-z]?(?:\([0-9A-Za-z]+\))*)",
    re.IGNORECASE,
)
HISTORICAL_QUERY_RE = re.compile(
    r"\b(historical|previous version|former|before amendment|at the time|as at|repealed)\b",
    re.I,
)


def _rrf(lists: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for ranked in lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] += 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)


def _source_filter(input_data: SearchInput) -> dict[str, Any]:
    source_category = input_data.sourceCategory or "official_legal_source"
    result: dict[str, Any] = {
        "active": True,
        "status": "approved",
        "deletedAt": {"$exists": False},
        "sourceCategory": source_category,
    }
    if source_category == "official_legal_source":
        result["legalReviewed"] = True
    for key in ("jurisdiction", "stateOrTerritory", "legalDomain", "pathwayCategory", "topic"):
        value = getattr(input_data, key)
        if value:
            result[key] = value
    if input_data.sourceIds:
        ids = [ObjectId(item) for item in input_data.sourceIds if ObjectId.is_valid(item)]
        result["_id"] = {"$in": ids}
    return result


def _chunk_to_result(
    chunk: dict[str, Any],
    source: dict[str, Any],
    score: float | None = None,
) -> dict[str, Any]:
    metadata = chunk.get("metadata") or {}
    return {
        "chunkId": str(chunk["_id"]),
        "sourceId": str(chunk["sourceId"]),
        "title": source.get("title", ""),
        "sourceTitle": source.get("sourceTitle") or source.get("title", ""),
        "publisher": source.get("publisher", ""),
        "sourceAuthority": source.get("sourceAuthority") or source.get("publisher", ""),
        "sourceCategory": source.get("sourceCategory"),
        "sourceType": source.get("sourceType"),
        "jurisdiction": source.get("jurisdiction"),
        "stateOrTerritory": source.get("stateOrTerritory"),
        "pathwayCategory": source.get("pathwayCategory"),
        "legalDomain": source.get("legalDomain"),
        "topic": source.get("topic"),
        "legislationName": source.get("legislationName") or source.get("title"),
        "sectionRef": chunk.get("sectionRef"),
        "sectionTitle": chunk.get("sectionTitle"),
        "lastUpdated": json_safe(source.get("lastUpdated")),
        "versionDate": json_safe(
            metadata.get("versionDate")
            or source.get("lastUpdated")
            or (source.get("metadata") or {}).get("effectiveDate")
        ),
        "commencementDate": metadata.get("commencementDate"),
        "amendmentStatus": metadata.get("amendmentStatus"),
        "amendingInstrument": metadata.get("amendingInstrument"),
        "crossReferences": metadata.get("crossReferences") or [],
        "citationUrl": chunk.get("citationUrl")
        or source.get("officialUrl")
        or source.get("url"),
        "text": chunk.get("chunkText", ""),
        "score": score,
        "pageNumber": chunk.get("pageNumber") or metadata.get("pageStart"),
        "extractionMethod": chunk.get("extractionMethod"),
        "metadata": json_safe(metadata),
    }


async def hybrid_search(input_data: SearchInput) -> list[dict[str, Any]]:
    database = get_database()
    sources = await database[SOURCE_COLLECTION].find(_source_filter(input_data)).to_list(length=500)
    if not sources:
        return []
    source_by_id = {str(source["_id"]): source for source in sources}
    source_ids = list(source_by_id)
    chunk_filter: dict[str, Any] = {
        "sourceId": {"$in": [ObjectId(item) for item in source_ids]},
        "active": True,
    }

    candidate_limit = max(
        input_data.topK * 4,
        get_settings().RAG_RERANK_CANDIDATES,
    )
    rankings: list[list[str]] = []
    vector_scores: dict[str, float] = {}

    if pinecone_store.configured and get_settings().OPENAI_API_KEY:
        try:
            query_vector = (await embedding_service.embed([input_data.query]))[0]
            # Source IDs came from the governed Mongo query, so approval and review
            # changes take effect immediately without requiring a Pinecone reindex.
            pinecone_filter: dict[str, Any] = {
                "sourceId": {"$in": source_ids},
                "active": {"$eq": True},
            }
            matches = await pinecone_store.query(
                query_vector,
                candidate_limit,
                pinecone_filter,
            )
            vector_ranking = []
            for match in matches:
                if match["score"] >= get_settings().RAG_MIN_SCORE_LEGAL:
                    chunk_id = str(match["metadata"].get("chunkId") or match["id"])
                    vector_ranking.append(chunk_id)
                    vector_scores[chunk_id] = match["score"]
            if vector_ranking:
                rankings.append(vector_ranking)
        except Exception:
            # Exact and Mongo keyword channels remain available during a provider outage.
            pass

    exact_sections = SECTION_QUERY_RE.findall(input_data.query)
    if exact_sections:
        base_sections = [section.split("(")[0] for section in exact_sections]
        exact_cursor = database[CHUNK_COLLECTION].find(
            {
                **chunk_filter,
                "$or": [
                    {"sectionRef": {"$in": exact_sections}},
                    {"sectionNumber": {"$in": base_sections}},
                ],
            },
            {"_id": 1},
        ).limit(candidate_limit)
        exact_ids = [str(item["_id"]) async for item in exact_cursor]
        if exact_ids:
            rankings.insert(0, exact_ids)

    try:
        text_cursor = (
            database[CHUNK_COLLECTION]
            .find(
                {**chunk_filter, "$text": {"$search": input_data.query}},
                {"score": {"$meta": "textScore"}},
            )
            .sort("score", {"$meta": "textScore"})
            .limit(candidate_limit)
        )
        text_ids = [str(item["_id"]) async for item in text_cursor]
        if text_ids:
            rankings.append(text_ids)
    except OperationFailure:
        tokens = [
            token
            for token in re.findall(r"[A-Za-z0-9]{3,}", input_data.query)
            if token.lower() not in {"what", "when", "where", "which", "that", "this"}
        ][:6]
        if tokens:
            fallback = (
                database[CHUNK_COLLECTION]
                .find(
                    {
                        **chunk_filter,
                        "$or": [
                            {"chunkText": {"$regex": re.escape(token), "$options": "i"}}
                            for token in tokens
                        ],
                    },
                    {"_id": 1},
                )
                .limit(candidate_limit)
            )
            fallback_ids = [str(item["_id"]) async for item in fallback]
            if fallback_ids:
                rankings.append(fallback_ids)

    if not rankings:
        return []
    ordered_ids = _rrf(rankings)
    object_ids = [ObjectId(item) for item in ordered_ids if ObjectId.is_valid(item)]
    chunks = await database[CHUNK_COLLECTION].find(
        {"_id": {"$in": object_ids}},
        {"embedding": 0},
    ).to_list(length=len(object_ids))
    chunk_by_id = {str(chunk["_id"]): chunk for chunk in chunks}

    candidates: list[dict[str, Any]] = []
    historical_query = bool(HISTORICAL_QUERY_RE.search(input_data.query))
    for chunk_id in ordered_ids:
        chunk = chunk_by_id.get(chunk_id)
        if not chunk:
            continue
        source_id = str(chunk["sourceId"])
        source = source_by_id.get(source_id)
        if not source:
            continue
        result = _chunk_to_result(chunk, source, vector_scores.get(chunk_id))
        if (
            not historical_query
            and (result.get("metadata") or {}).get("amendmentStatus") == "repealed"
        ):
            continue
        candidates.append(result)
        if len(candidates) >= candidate_limit:
            break
    reranked = await rerank_results(input_data.query, candidates, candidate_limit)
    results: list[dict[str, Any]] = []
    source_counts: dict[str, int] = defaultdict(int)
    for result in reranked:
        source_id = str(result.get("sourceId"))
        if source_counts[source_id] >= get_settings().RAG_MAX_CHUNKS_PER_SOURCE:
            continue
        results.append(result)
        source_counts[source_id] += 1
        if len(results) >= input_data.topK:
            break
    return results
