import asyncio
from pathlib import Path

from fastapi import UploadFile

from app.agents.assistant_graph import run_timeline_assistant
from app.agents.rag_graph import answer_question
from app.services.knowledge import (
    create_source as legacy_create_source,
)
from app.services.knowledge import (
    delete_source as legacy_delete_source,
)
from app.services.knowledge import (
    get_source_artifacts as legacy_get_source_artifacts,
)
from app.services.knowledge import (
    ingest_text as legacy_ingest_text,
)
from app.services.knowledge import (
    list_chunks as legacy_list_chunks,
)
from app.services.knowledge import (
    list_sources as legacy_list_sources,
)
from app.services.knowledge import (
    reindex_source as legacy_reindex_source,
)
from app.services.knowledge import (
    update_source as legacy_update_source,
)
from app.services.knowledge import (
    upload_and_ingest as legacy_upload_and_ingest,
)
from app.services.legal_readiness import assert_legal_runtime_ready
from app.services.retrieval import hybrid_search

from .governance import (
    approve_knowledge_source as approve_knowledge_source_governance,
)
from .governance import (
    approve_ocr_knowledge_source as approve_ocr_knowledge_source_governance,
)
from .governance import (
    get_knowledge_source_ocr_preview,
    get_knowledge_source_readiness,
    get_knowledge_source_status,
    get_pinecone_health,
)
from .governance import (
    reject_knowledge_source as reject_knowledge_source_governance,
)
from .governance import (
    run_knowledge_source_ocr as run_knowledge_source_ocr_governance,
)
from .schema import (
    AnswerInput,
    KnowledgeIngestInput,
    KnowledgeRefreshInput,
    KnowledgeSourceCreate,
    KnowledgeSourceUpdate,
    RagDebugRetrieveInput,
    SearchInput,
    TimelineAssistantInput,
)


async def search_rag(request: SearchInput) -> list[dict]:
    assert_legal_runtime_ready()
    return await hybrid_search(request)


async def answer_rag(request: AnswerInput) -> dict:
    assert_legal_runtime_ready()
    return await answer_question(request)


async def timeline_assistant_rag(request: TimelineAssistantInput) -> dict:
    return await run_timeline_assistant(request)


async def debug_retrieve_rag(request: RagDebugRetrieveInput) -> dict:
    results = await search_rag(SearchInput.model_validate(request.model_dump()))
    return {
        "query": request.query,
        "topK": request.topK,
        "resultCount": len(results),
        "results": results,
        "filters": {
            key: value
            for key, value in request.model_dump().items()
            if key not in {"query", "topK"} and value not in (None, [], {})
        },
    }


async def list_knowledge_sources() -> list[dict]:
    return await legacy_list_sources()


async def create_knowledge_source(request: KnowledgeSourceCreate, actor_id: str | None) -> dict:
    return await legacy_create_source(request, actor_id)


async def update_knowledge_source(source_id: str, request: KnowledgeSourceUpdate) -> dict:
    return await legacy_update_source(source_id, request)


async def delete_knowledge_source(source_id: str) -> None:
    await legacy_delete_source(source_id)


async def list_knowledge_source_chunks(source_id: str, page: int, limit: int) -> dict:
    return await legacy_list_chunks(source_id, page, limit)


async def get_knowledge_source_artifacts(source_id: str) -> dict:
    return await legacy_get_source_artifacts(source_id)


async def upload_knowledge_source_document(
    source_id: str,
    file: UploadFile,
    *,
    ingest_immediately: bool,
) -> dict:
    return await legacy_upload_and_ingest(
        source_id,
        file,
        ingest_immediately=ingest_immediately,
    )


async def ingest_knowledge_source(source_id: str, request: KnowledgeIngestInput) -> dict:
    if request.content:
        return await legacy_ingest_text(source_id, request.content, request.expectedSha256)
    if request.localFilePath:
        content = await asyncio.to_thread(
            Path(request.localFilePath).read_text,
            encoding="utf-8",
        )
        return await legacy_ingest_text(source_id, content, request.expectedSha256)
    return await legacy_reindex_source(source_id)


async def refresh_knowledge_source(source_id: str, request: KnowledgeRefreshInput) -> dict:
    if request.content:
        return await legacy_ingest_text(source_id, request.content, request.expectedSha256)
    return await legacy_reindex_source(source_id)


async def reindex_knowledge_source(source_id: str) -> dict:
    return await legacy_reindex_source(source_id)


async def approve_knowledge_source(source_id: str, actor_id: str) -> dict:
    return await approve_knowledge_source_governance(source_id, actor_id)


async def reject_knowledge_source(source_id: str, actor_id: str, reason: str) -> dict:
    return await reject_knowledge_source_governance(source_id, actor_id, reason)


async def run_knowledge_source_ocr(source_id: str, request) -> dict:
    return await run_knowledge_source_ocr_governance(source_id, request)


async def approve_ocr_knowledge_source(
    source_id: str,
    actor_id: str,
    *,
    legal_reviewed: bool,
) -> dict:
    return await approve_ocr_knowledge_source_governance(
        source_id,
        actor_id,
        legal_reviewed=legal_reviewed,
    )


async def rag_pinecone_health() -> dict:
    return await get_pinecone_health()


async def rag_readiness() -> dict:
    return await get_knowledge_source_readiness()


async def rag_status(source_id: str) -> dict:
    return await get_knowledge_source_status(source_id)


async def rag_ocr_preview(source_id: str, *, page: int, page_size: int) -> dict:
    return await get_knowledge_source_ocr_preview(
        source_id,
        page=page,
        page_size=page_size,
    )
