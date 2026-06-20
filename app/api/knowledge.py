import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.responses import success
from app.core.security import Principal, require_content_admin
from app.models.knowledge import (
    KnowledgeIngestInput,
    KnowledgeRefreshInput,
    KnowledgeSourceCreate,
    KnowledgeSourceUpdate,
    RejectInput,
)
from app.services.knowledge import (
    create_source,
    delete_source,
    get_source,
    get_source_artifacts,
    ingest_text,
    list_chunks,
    list_sources,
    readiness,
    reindex_source,
    set_approval,
    update_source,
    upload_and_ingest,
)
from app.services.serialization import json_safe
from app.services.vector_store import pinecone_store

router = APIRouter(prefix="/rag", tags=["knowledge"])
Admin = Annotated[Principal, Depends(require_content_admin)]


@router.get("/admin/pinecone/health")
async def pinecone_health(_principal: Admin):
    return success("Pinecone health retrieved", {"health": await pinecone_store.health()})


@router.get("/knowledge-sources")
async def sources(_principal: Admin):
    return success("Knowledge sources retrieved", {"sources": await list_sources()})


@router.get("/knowledge-sources/readiness")
async def source_readiness(_principal: Admin):
    return success("Knowledge source readiness retrieved", {"readiness": await readiness()})


@router.post("/knowledge-sources", status_code=status.HTTP_201_CREATED)
async def source_create(request: KnowledgeSourceCreate, principal: Admin):
    source = await create_source(request, principal.user_id)
    return success("Knowledge source created", {"source": source})


@router.patch("/knowledge-sources/{source_id}")
async def source_update(source_id: str, request: KnowledgeSourceUpdate, _principal: Admin):
    source = await update_source(source_id, request)
    return success("Knowledge source updated", {"source": source})


@router.delete("/knowledge-sources/{source_id}")
async def source_delete(source_id: str, _principal: Admin):
    await delete_source(source_id)
    return success("Knowledge source deleted", None)


@router.get("/knowledge-sources/{source_id}/chunks")
async def source_chunks(
    source_id: str,
    _principal: Admin,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=50),
):
    return success(
        "Knowledge source chunks retrieved",
        await list_chunks(source_id, page, limit),
    )


@router.get("/knowledge-sources/{source_id}/artifacts")
async def source_artifacts(source_id: str, _principal: Admin):
    return success(
        "Knowledge source extraction artifacts retrieved",
        {"artifacts": await get_source_artifacts(source_id)},
    )


@router.post("/knowledge-sources/{source_id}/document")
async def source_document(
    source_id: str,
    _principal: Admin,
    file: Annotated[UploadFile, File(...)],
):
    result = await upload_and_ingest(source_id, file)
    return success(
        "Knowledge source document uploaded",
        {"result": result},
        {"informationOnly": True},
    )


@router.post("/knowledge-sources/{source_id}/ingest")
async def source_ingest(
    source_id: str,
    request: KnowledgeIngestInput,
    _principal: Admin,
):
    if request.content:
        result = await ingest_text(source_id, request.content, request.expectedSha256)
    elif request.localFilePath:
        content = await asyncio.to_thread(
            Path(request.localFilePath).read_text,
            encoding="utf-8",
        )
        result = await ingest_text(source_id, content, request.expectedSha256)
    else:
        result = await reindex_source(source_id)
    return success("Knowledge source ingested", {"result": result}, {"informationOnly": True})


@router.post("/knowledge-sources/{source_id}/refresh")
async def source_refresh(
    source_id: str,
    request: KnowledgeRefreshInput,
    _principal: Admin,
):
    result = (
        await ingest_text(source_id, request.content, request.expectedSha256)
        if request.content
        else await reindex_source(source_id)
    )
    return success("Knowledge source refreshed", {"result": result}, {"informationOnly": True})


@router.post("/knowledge-sources/{source_id}/reindex")
async def source_reindex(source_id: str, _principal: Admin):
    result = await reindex_source(source_id)
    return success("Knowledge source reindexed", {"result": result}, {"informationOnly": True})


@router.post("/knowledge-sources/{source_id}/approve")
async def source_approve(source_id: str, principal: Admin):
    source = await set_approval(source_id, principal.user_id or "", True)
    return success("Knowledge source approved", {"source": source})


@router.post("/knowledge-sources/{source_id}/reject")
async def source_reject(source_id: str, request: RejectInput, principal: Admin):
    source = await set_approval(source_id, principal.user_id or "", False, request.reason)
    return success("Knowledge source rejected", {"source": source})


@router.get("/knowledge-sources/{source_id}/status")
async def source_status(source_id: str, _principal: Admin):
    source = json_safe(await get_source(source_id))
    return success(
        "Knowledge source status retrieved",
        {
            "status": {
                "sourceId": source_id,
                "ingestionStatus": source.get("ingestionStatus"),
                "processingStage": (source.get("metadata") or {}).get("processingStage"),
                "metadata": source.get("metadata", {}),
            }
        },
    )
