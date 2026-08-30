from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.extraction import ocr_health
from app.services.knowledge import get_source, readiness, reindex_source, set_approval
from app.services.serialization import json_safe

from .repository import RagRepository, get_rag_repository


async def get_knowledge_source_readiness() -> dict[str, Any]:
    return await readiness()


async def get_pinecone_health(repository: RagRepository | None = None) -> dict[str, Any]:
    repository = repository or get_rag_repository()
    return await repository.pinecone_health()


async def approve_knowledge_source(source_id: str, actor_id: str) -> dict[str, Any]:
    return await set_approval(source_id, actor_id, True)


async def reject_knowledge_source(source_id: str, actor_id: str, reason: str) -> dict[str, Any]:
    return await set_approval(source_id, actor_id, False, reason)


async def run_knowledge_source_ocr(
    source_id: str,
    _input_data: Any,
    *,
    repository: RagRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_rag_repository()
    source = await get_source(source_id)
    if not source.get("localFilePath") and not source.get("rawText"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Knowledge source does not have stored content available for OCR or re-extraction.",
        )
    result = await reindex_source(source_id)
    refreshed = await repository.get_source(source_id)
    metadata = (refreshed or {}).get("metadata") or {}
    extraction_method = str((refreshed or {}).get("extractionMethod") or "")
    ocr_used = extraction_method.endswith("_ocr")
    await repository.update_source(
        source_id,
        {
            "ocrStatus": "completed" if ocr_used else "not_required",
            "ocrProvider": "pymupdf_tesseract" if ocr_used else None,
            "ocrAverageConfidence": metadata.get("ocrAverageConfidence"),
        },
    )
    return {
        "sourceId": source_id,
        "ocrStatus": "completed" if ocr_used else "not_required",
        "ocrProvider": "pymupdf_tesseract" if ocr_used else None,
        "ocrAverageConfidence": metadata.get("ocrAverageConfidence"),
        "pageCount": metadata.get("extractedPageCount"),
        "result": result,
        "health": ocr_health(),
    }


async def approve_ocr_knowledge_source(
    source_id: str,
    actor_id: str,
    *,
    legal_reviewed: bool,
    repository: RagRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_rag_repository()
    source = await repository.get_source(source_id)
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge source not found")
    extraction = await repository.get_extraction(source_id)
    if not extraction:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Knowledge source does not have OCR output to approve.",
        )
    metadata = source.get("metadata") or {}
    await repository.update_source(
        source_id,
        {
            "legalReviewed": legal_reviewed,
            "ocrStatus": "reviewed",
            "metadata": {
                **metadata,
                "ocrReviewedBy": actor_id,
                "ocrReviewedAt": source.get("updatedAt"),
            },
        },
    )
    refreshed = await repository.get_source(source_id)
    return json_safe(refreshed or source)


async def get_knowledge_source_ocr_preview(
    source_id: str,
    *,
    page: int,
    page_size: int,
    repository: RagRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_rag_repository()
    extraction = await repository.get_extraction(source_id)
    if not extraction or not extraction.get("structured"):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Knowledge source OCR preview is not available.",
        )
    pages = extraction["structured"].get("pages") or []
    start = (page - 1) * page_size
    selected = pages[start : start + page_size]
    return {
        "page": page,
        "pageSize": page_size,
        "totalCount": len(pages),
        "totalPages": max(1, (len(pages) + page_size - 1) // page_size),
        "pages": [
            {
                "number": item.get("number"),
                "text": item.get("text"),
                "ocrUsed": item.get("ocrUsed"),
                "ocrConfidence": item.get("ocrConfidence"),
                "warnings": item.get("warnings") or [],
            }
            for item in selected
        ],
    }


async def get_knowledge_source_status(
    source_id: str,
    *,
    repository: RagRepository | None = None,
) -> dict[str, Any]:
    source = json_safe(await get_source(source_id))
    metadata = source.get("metadata") or {}
    uploaded_file = metadata.get("uploadedFile") or {}
    uploaded_file_name = str(uploaded_file.get("originalFileName") or "")
    uploaded_file_size = uploaded_file.get("fileSizeBytes")
    storage_key = str(uploaded_file.get("storageKey") or "")
    local_file_path = str(source.get("localFilePath") or "")
    candidate_path = (
        Path(local_file_path)
        if local_file_path
        else get_settings().KNOWLEDGE_STORAGE_PATH / storage_key
        if storage_key
        else None
    )
    uploaded_file_exists = bool(candidate_path and candidate_path.exists())
    raw_text = str(source.get("rawText") or "")
    integrity_warnings: list[str] = []
    likely_sample_document = False

    if uploaded_file_name.lower().endswith(".pdf") and source.get("extractionMethod") == "manual":
        integrity_warnings.append(
            "This PDF source is marked as manual extraction, not full PDF parsing."
        )
    if (
        isinstance(uploaded_file_size, int)
        and uploaded_file_name.lower().endswith(".pdf")
        and uploaded_file_size < 10_000
    ):
        likely_sample_document = True
        integrity_warnings.append(
            "This uploaded PDF is very small and looks like a smoke-test or "
            "sample file, not a full document."
        )
    if uploaded_file_name and not uploaded_file_exists:
        integrity_warnings.append(
            "The stored uploaded file is missing from knowledge storage, so "
            "re-extraction from the original file is not currently possible."
        )
    if (
        uploaded_file_name.lower().endswith(".pdf")
        and isinstance(uploaded_file_size, int)
        and uploaded_file_size > 100_000
        and len(raw_text) < 1000
    ):
        integrity_warnings.append(
            "The extracted text is unusually short for the uploaded PDF size. "
            "Review extraction completeness."
        )

    return {
        "id": source.get("id") or source_id,
        "sourceId": source_id,
        "sourceTitle": source.get("sourceTitle") or source.get("title"),
        "ingestionStatus": source.get("ingestionStatus"),
        "legalReviewed": bool(source.get("legalReviewed")),
        "active": bool(source.get("active", True)),
        "status": source.get("status"),
        "extractionMethod": source.get("extractionMethod"),
        "ocrStatus": source.get("ocrStatus", "not_required"),
        "ocrPageCount": metadata.get("extractedPageCount"),
        "ocrWarnings": metadata.get("extractionWarnings", []),
        "embeddingModel": source.get("embeddingModel"),
        "pineconeIndex": source.get("pineconeIndex"),
        "pineconeNamespace": source.get("pineconeNamespace"),
        "indexSyncStatus": metadata.get("indexSyncStatus"),
        "mongoChunkCount": metadata.get("mongoChunkCount", metadata.get("chunkCount")),
        "pineconeVectorCount": metadata.get("pineconeVectorCount"),
        "lastIndexedAt": metadata.get("lastIndexedAt"),
        "processingStage": metadata.get("processingStage"),
        "ingestionError": source.get("ingestionError"),
        "uploadedFileExists": uploaded_file_exists,
        "uploadedFileSizeBytes": uploaded_file_size,
        "rawTextLength": len(raw_text),
        "likelySampleDocument": likely_sample_document,
        "integrityWarnings": integrity_warnings,
        "metadata": metadata,
    }
