from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.core.responses import success

from .dependencies import CurrentRagAdminPrincipal, CurrentRagInternal, CurrentRagPrincipal
from .schema import (
    AnswerInput,
    ApproveOcrKnowledgeSourceInput,
    KnowledgeIngestInput,
    KnowledgeRefreshInput,
    KnowledgeSourceCreate,
    KnowledgeSourceUpdate,
    RagDebugRetrieveInput,
    RejectInput,
    RunKnowledgeSourceOcrInput,
    SearchInput,
    TimelineAssistantInput,
)
from .service import (
    answer_rag,
    approve_knowledge_source,
    approve_ocr_knowledge_source,
    create_knowledge_source,
    debug_retrieve_rag,
    delete_knowledge_source,
    get_knowledge_source_artifacts,
    get_knowledge_source_ocr_preview,
    get_knowledge_source_readiness,
    get_knowledge_source_status,
    get_pinecone_health,
    ingest_knowledge_source,
    list_knowledge_source_chunks,
    list_knowledge_sources,
    refresh_knowledge_source,
    reindex_knowledge_source,
    reject_knowledge_source,
    run_knowledge_source_ocr,
    search_rag,
    timeline_assistant_rag,
    update_knowledge_source,
    upload_knowledge_source_document,
)

router = APIRouter(prefix="/rag", tags=["rag"])
internal_router = APIRouter(prefix="/internal/rag", tags=["internal-rag"])


@router.post("/search")
async def search(request: SearchInput, _principal: CurrentRagPrincipal):
    return success(
        "RAG search completed",
        {"results": await search_rag(request)},
        {"informationOnly": True, "citationsRequired": True},
    )


@router.post("/answer")
async def answer(request: AnswerInput, _principal: CurrentRagPrincipal):
    return success("RAG answer generated", await answer_rag(request), {"informationOnly": True})


@router.post("/timeline-assistant")
async def timeline_assistant(
    request: TimelineAssistantInput,
    _principal: CurrentRagPrincipal,
):
    return success(
        "Timeline assistant response generated",
        await timeline_assistant_rag(request),
        {"informationOnly": True},
    )


@router.post("/debug/retrieve")
async def debug_retrieve(
    request: RagDebugRetrieveInput,
    _principal: CurrentRagAdminPrincipal,
):
    return success(
        "RAG debug retrieval completed",
        await debug_retrieve_rag(request),
        {"informationOnly": True},
    )


@router.get("/admin/pinecone/health")
async def pinecone_health(_principal: CurrentRagAdminPrincipal):
    return success("Pinecone health retrieved", {"health": await get_pinecone_health()})


@router.get("/knowledge-sources")
async def sources(_principal: CurrentRagAdminPrincipal):
    return success("Knowledge sources retrieved", {"sources": await list_knowledge_sources()})


@router.get("/knowledge-sources/readiness")
async def source_readiness(_principal: CurrentRagAdminPrincipal):
    return success(
        "Knowledge source readiness retrieved",
        {"readiness": await get_knowledge_source_readiness()},
    )


@router.post("/knowledge-sources", status_code=status.HTTP_201_CREATED)
async def source_create(
    request: KnowledgeSourceCreate,
    principal: CurrentRagAdminPrincipal,
):
    source = await create_knowledge_source(request, principal.user_id)
    return success("Knowledge source created", {"source": source})


@router.patch("/knowledge-sources/{source_id}")
async def source_update(
    source_id: str,
    request: KnowledgeSourceUpdate,
    _principal: CurrentRagAdminPrincipal,
):
    source = await update_knowledge_source(source_id, request)
    return success("Knowledge source updated", {"source": source})


@router.delete("/knowledge-sources/{source_id}")
async def source_delete(source_id: str, _principal: CurrentRagAdminPrincipal):
    await delete_knowledge_source(source_id)
    return success("Knowledge source deleted", None)


@router.get("/knowledge-sources/{source_id}/chunks")
async def source_chunks(
    source_id: str,
    _principal: CurrentRagAdminPrincipal,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=50),
):
    return success(
        "Knowledge source chunks retrieved",
        await list_knowledge_source_chunks(source_id, page, limit),
    )


@router.get("/knowledge-sources/{source_id}/artifacts")
async def source_artifacts(source_id: str, _principal: CurrentRagAdminPrincipal):
    return success(
        "Knowledge source extraction artifacts retrieved",
        {"artifacts": await get_knowledge_source_artifacts(source_id)},
    )


@router.post("/knowledge-sources/{source_id}/document")
async def source_document(
    source_id: str,
    _principal: CurrentRagAdminPrincipal,
    file: Annotated[UploadFile, File(...)],
    ingest_immediately: Annotated[bool, Form(alias="ingestImmediately")] = True,
):
    result = await upload_knowledge_source_document(
        source_id,
        file,
        ingest_immediately=ingest_immediately,
    )
    return success(
        "Knowledge source document uploaded",
        {"result": result},
        {"informationOnly": True},
    )


@router.post("/knowledge-sources/{source_id}/ingest")
async def source_ingest(
    source_id: str,
    request: KnowledgeIngestInput,
    _principal: CurrentRagAdminPrincipal,
):
    return success(
        "Knowledge source ingested",
        {"result": await ingest_knowledge_source(source_id, request)},
        {"informationOnly": True},
    )


@router.post("/knowledge-sources/{source_id}/refresh")
async def source_refresh(
    source_id: str,
    request: KnowledgeRefreshInput,
    _principal: CurrentRagAdminPrincipal,
):
    return success(
        "Knowledge source refreshed",
        {"result": await refresh_knowledge_source(source_id, request)},
        {"informationOnly": True},
    )


@router.post("/knowledge-sources/{source_id}/reindex")
async def source_reindex(source_id: str, _principal: CurrentRagAdminPrincipal):
    return success(
        "Knowledge source reindexed",
        {"result": await reindex_knowledge_source(source_id)},
        {"informationOnly": True},
    )


@router.post("/knowledge-sources/{source_id}/approve")
async def source_approve(source_id: str, principal: CurrentRagAdminPrincipal):
    source = await approve_knowledge_source(source_id, principal.user_id or "")
    return success("Knowledge source approved", {"source": source})


@router.post("/knowledge-sources/{source_id}/reject")
async def source_reject(
    source_id: str,
    request: RejectInput,
    principal: CurrentRagAdminPrincipal,
):
    source = await reject_knowledge_source(
        source_id,
        principal.user_id or "",
        request.reason,
    )
    return success("Knowledge source rejected", {"source": source})


@router.post("/knowledge-sources/{source_id}/ocr")
async def source_ocr(
    source_id: str,
    request: RunKnowledgeSourceOcrInput,
    _principal: CurrentRagAdminPrincipal,
):
    return success(
        "Knowledge source OCR completed",
        {"result": await run_knowledge_source_ocr(source_id, request)},
        {"informationOnly": True},
    )


@router.post("/knowledge-sources/{source_id}/ocr/approve")
async def source_ocr_approve(
    source_id: str,
    request: ApproveOcrKnowledgeSourceInput,
    principal: CurrentRagAdminPrincipal,
):
    source = await approve_ocr_knowledge_source(
        source_id,
        principal.user_id or "",
        legal_reviewed=request.legalReviewed,
    )
    return success("Knowledge source OCR approved", {"source": source})


@router.get("/knowledge-sources/{source_id}/ocr-preview")
async def source_ocr_preview(
    source_id: str,
    _principal: CurrentRagAdminPrincipal,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=20, alias="pageSize"),
):
    return success(
        "Knowledge source OCR preview retrieved",
        {
            "preview": await get_knowledge_source_ocr_preview(
                source_id,
                page=page,
                page_size=page_size,
            )
        },
    )


@router.get("/knowledge-sources/{source_id}/status")
async def source_status(source_id: str, _principal: CurrentRagAdminPrincipal):
    return success(
        "Knowledge source status retrieved",
        {"status": await get_knowledge_source_status(source_id)},
    )


@internal_router.post("/search")
async def internal_search(request: SearchInput, _authorized: CurrentRagInternal):
    return success(
        "RAG search completed",
        {"results": await search_rag(request)},
        {"informationOnly": True, "citationsRequired": True},
    )


@internal_router.post("/answer")
async def internal_answer(request: AnswerInput, _authorized: CurrentRagInternal):
    return success("RAG answer generated", await answer_rag(request), {"informationOnly": True})


@internal_router.post("/timeline-assistant")
async def internal_timeline_assistant(
    request: TimelineAssistantInput,
    _authorized: CurrentRagInternal,
):
    return success(
        "Timeline assistant response generated",
        await timeline_assistant_rag(request),
        {"informationOnly": True},
    )
