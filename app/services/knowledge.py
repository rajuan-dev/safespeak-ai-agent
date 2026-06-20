import asyncio
import hashlib
import mimetypes
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from pymongo import ASCENDING, TEXT, UpdateOne

from app.core.config import get_settings
from app.core.database import get_database
from app.models.extraction import ExtractedDocument
from app.models.knowledge import KnowledgeSourceCreate, KnowledgeSourceUpdate
from app.services.chunking import chunk_extracted_document, chunk_plain_text
from app.services.embeddings import embedding_service
from app.services.extraction import extract_pdf, ocr_health
from app.services.legal_metadata import build_structure_tree
from app.services.legal_readiness import golden_report_health
from app.services.serialization import json_safe
from app.services.vector_store import pinecone_store

SOURCE_COLLECTION = "ragknowledgesources"
CHUNK_COLLECTION = "ragchunks"
EXTRACTION_COLLECTION = "ragextracteddocuments"
STRUCTURE_COLLECTION = "ragsourcestructures"


def _object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid ObjectId")
    return ObjectId(value)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    # Older MongoDB records may decode as naive UTC datetimes.
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _source_fields(source: dict[str, Any]) -> dict[str, Any]:
    names = (
        "sourceCategory",
        "sourceAuthority",
        "officialUrl",
        "country",
        "jurisdiction",
        "stateOrTerritory",
        "pathwayCategory",
        "legalDomain",
        "topic",
        "legislationName",
        "sourceType",
    )
    return {name: source.get(name) for name in names if source.get(name) is not None}


async def ensure_indexes() -> None:
    database = get_database()
    chunks = database[CHUNK_COLLECTION]
    sources = database[SOURCE_COLLECTION]
    await chunks.create_index([("sourceId", ASCENDING), ("chunkIndex", ASCENDING)], unique=True)
    existing_indexes = await chunks.index_information()
    keyword_index = existing_indexes.get("rag_chunk_keyword_text")
    if keyword_index and "definedTerms" not in keyword_index.get("weights", {}):
        await chunks.drop_index("rag_chunk_keyword_text")
    await chunks.create_index(
        [
            ("sectionRef", TEXT),
            ("sectionTitle", TEXT),
            ("legislationName", TEXT),
            ("definedTerms", TEXT),
            ("chunkText", TEXT),
        ],
        name="rag_chunk_keyword_text",
        weights={
            "sectionRef": 12,
            "definedTerms": 10,
            "sectionTitle": 6,
            "legislationName": 4,
            "chunkText": 1,
        },
        default_language="english",
    )
    await sources.create_index([("status", ASCENDING), ("active", ASCENDING)])
    await database[STRUCTURE_COLLECTION].create_index("sourceId", unique=True)


async def _resolve_cross_references(
    source: dict[str, Any],
    documents: list[dict[str, Any]],
) -> None:
    collection = get_database()[CHUNK_COLLECTION]
    operations = []
    for document in documents:
        metadata = document.get("metadata") or {}
        references = metadata.get("crossReferences") or []
        changed = False
        for reference in references:
            section_ref = reference.get("sectionRef")
            if not section_ref:
                continue
            act_name = str(reference.get("actName") or "").strip()
            current_names = {
                str(source.get("title") or "").casefold(),
                str(source.get("legislationName") or "").casefold(),
            }
            target_filter: dict[str, Any] = {
                "active": True,
                "$or": [
                    {"sectionRef": section_ref},
                    {"sectionNumber": section_ref.split("(")[0]},
                ],
            }
            if not act_name or act_name.casefold() in current_names:
                target_filter["sourceId"] = source["_id"]
            else:
                target_source = await get_database()[SOURCE_COLLECTION].find_one(
                    {
                        "$or": [
                            {"title": {"$regex": f"^{re.escape(act_name)}$", "$options": "i"}},
                            {
                                "legislationName": {
                                    "$regex": f"^{re.escape(act_name)}$",
                                    "$options": "i",
                                }
                            },
                        ]
                    },
                    {"_id": 1},
                )
                if target_source:
                    target_filter["sourceId"] = target_source["_id"]
                else:
                    target_filter["legislationName"] = {
                        "$regex": f"^{re.escape(act_name)}$",
                        "$options": "i",
                    }
            target = await collection.find_one(
                target_filter,
                {"_id": 1, "sourceId": 1, "sectionRef": 1, "legislationName": 1},
            )
            if target:
                reference.update(
                    {
                        "resolutionStatus": "resolved",
                        "targetChunkId": str(target["_id"]),
                        "targetSourceId": str(target["sourceId"]),
                        "targetSectionRef": target.get("sectionRef"),
                        "targetActName": target.get("legislationName"),
                    }
                )
                changed = True
        if changed:
            operations.append(
                UpdateOne(
                    {"_id": document["_id"]},
                    {"$set": {"metadata.crossReferences": references}},
                )
            )
            document["metadata"]["crossReferences"] = references
    if operations:
        await collection.bulk_write(operations)


async def list_sources() -> list[dict[str, Any]]:
    cursor = get_database()[SOURCE_COLLECTION].find({"deletedAt": {"$exists": False}}).sort(
        "updatedAt", -1
    )
    return json_safe(await cursor.to_list(length=1000))


async def get_source(source_id: str) -> dict[str, Any]:
    source = await get_database()[SOURCE_COLLECTION].find_one(
        {"_id": _object_id(source_id), "deletedAt": {"$exists": False}}
    )
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge source not found")
    return source


async def create_source(data: KnowledgeSourceCreate, actor_id: str | None) -> dict[str, Any]:
    now = _now()
    document = data.model_dump(mode="python", exclude_none=True)
    for field in ("officialUrl", "url"):
        if field in document:
            document[field] = str(document[field])
    document.update(
        {
            "createdAt": now,
            "updatedAt": now,
            "createdBy": ObjectId(actor_id) if actor_id and ObjectId.is_valid(actor_id) else None,
            "ingestionStatus": "metadata_only",
            "extractionMethod": "text",
        }
    )
    result = await get_database()[SOURCE_COLLECTION].insert_one(document)
    return json_safe({**document, "_id": result.inserted_id})


async def update_source(source_id: str, data: KnowledgeSourceUpdate) -> dict[str, Any]:
    changes = data.model_dump(mode="python", exclude_none=True)
    for field in ("officialUrl", "url"):
        if field in changes:
            changes[field] = str(changes[field])
    if not changes:
        return json_safe(await get_source(source_id))
    changes["updatedAt"] = _now()
    document = await get_database()[SOURCE_COLLECTION].find_one_and_update(
        {"_id": _object_id(source_id), "deletedAt": {"$exists": False}},
        {"$set": changes},
        return_document=True,
    )
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge source not found")
    return json_safe(document)


async def delete_source(source_id: str) -> None:
    object_id = _object_id(source_id)
    source = await get_source(source_id)
    await pinecone_store.delete_source(source_id)
    database = get_database()
    await database[CHUNK_COLLECTION].delete_many({"sourceId": object_id})
    await database[EXTRACTION_COLLECTION].delete_many({"sourceId": object_id})
    await database[STRUCTURE_COLLECTION].delete_many({"sourceId": object_id})
    await database[SOURCE_COLLECTION].update_one(
        {"_id": object_id},
        {"$set": {"deletedAt": _now(), "active": False, "updatedAt": _now()}},
    )
    uploaded = (source.get("metadata") or {}).get("uploadedFile") or {}
    storage_key = uploaded.get("storageKey")
    if storage_key:
        path = get_settings().KNOWLEDGE_STORAGE_PATH / storage_key
        if path.resolve().is_relative_to(get_settings().KNOWLEDGE_STORAGE_PATH.resolve()):
            await asyncio.to_thread(path.unlink, missing_ok=True)


async def _replace_chunks(
    source: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    extraction_method: str,
) -> list[dict[str, Any]]:
    if not chunks:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No searchable text was extracted",
        )
    vectors = await embedding_service.embed([chunk["chunkText"] for chunk in chunks])
    now = _now()
    source_id = source["_id"]
    common = {
        **_source_fields(source),
        "sourceId": source_id,
        "sourceTitle": source.get("sourceTitle") or source.get("title"),
        "legislationName": source.get("legislationName") or source.get("title"),
        "legalReviewed": bool(source.get("legalReviewed")),
        "active": bool(source.get("active", True)),
        "extractionMethod": extraction_method,
        "embeddingModel": get_settings().OPENAI_EMBEDDING_MODEL,
        "pineconeIndex": get_settings().PINECONE_INDEX_NAME,
        "pineconeNamespace": get_settings().PINECONE_NAMESPACE,
        "citationUrl": source.get("officialUrl") or source.get("url"),
        "createdAt": now,
        "updatedAt": now,
    }
    documents = [
        {**common, **chunk, "embedding": vector}
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    database = get_database()
    await pinecone_store.delete_source(str(source_id))
    await database[CHUNK_COLLECTION].delete_many({"sourceId": source_id})
    result = await database[CHUNK_COLLECTION].insert_many(documents)
    for document, inserted_id in zip(documents, result.inserted_ids, strict=True):
        document["_id"] = inserted_id
    await _resolve_cross_references(source, documents)

    indexing_error = None
    pinecone_indexed_at = None
    if pinecone_store.configured:
        try:
            await pinecone_store.upsert(documents)
            pinecone_indexed_at = now
        except Exception as exc:
            indexing_error = str(exc)

    ingestion_status = "embedded" if not indexing_error else "partial_index_failed"
    await database[SOURCE_COLLECTION].update_one(
        {"_id": source_id},
        {
            "$set": {
                "ingestionStatus": ingestion_status,
                "ingestionError": indexing_error,
                "embeddingModel": get_settings().OPENAI_EMBEDDING_MODEL,
                "pineconeIndex": get_settings().PINECONE_INDEX_NAME,
                "pineconeNamespace": get_settings().PINECONE_NAMESPACE,
                "ingestedAt": now,
                "updatedAt": now,
                "metadata.chunkCount": len(documents),
                "metadata.mongoChunkCount": len(documents),
                "metadata.indexedChunkCount": len(documents) if not indexing_error else 0,
                "metadata.pineconeVectorCount": len(documents) if not indexing_error else 0,
                "metadata.pineconeIndexed": not indexing_error,
                "metadata.pineconeIndexedAt": pinecone_indexed_at,
                "metadata.lastIndexedAt": pinecone_indexed_at,
                "metadata.indexSyncStatus": "synced" if not indexing_error else "partial",
                "metadata.indexSyncError": indexing_error,
                "metadata.searchReadinessStatus": (
                    "searchable" if not indexing_error else "indexed_pending_search"
                ),
            }
        },
    )
    return documents


async def ingest_extraction(
    source_id: str,
    extracted: ExtractedDocument,
    *,
    uploaded_file: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = await get_source(source_id)
    chunks = chunk_extracted_document(extracted, source)
    legal_structure = build_structure_tree(chunks, source)
    documents = await _replace_chunks(
        source,
        chunks,
        extraction_method=extracted.extractionMethod,
    )
    now = _now()
    extraction_doc = {
        "sourceId": source["_id"],
        "sha256": extracted.sha256,
        "fileName": extracted.fileName,
        "pageCount": extracted.pageCount,
        "extractionMethod": extracted.extractionMethod,
        "rawText": extracted.rawText,
        "markdown": extracted.markdown,
        "structured": extracted.model_dump(mode="python"),
        "legalStructure": legal_structure,
        "createdAt": now,
        "updatedAt": now,
    }
    database = get_database()
    await database[EXTRACTION_COLLECTION].replace_one(
        {"sourceId": source["_id"]},
        extraction_doc,
        upsert=True,
    )
    await database[STRUCTURE_COLLECTION].replace_one(
        {"sourceId": source["_id"]},
        {
            "sourceId": source["_id"],
            "sha256": extracted.sha256,
            "structure": legal_structure,
            "createdAt": now,
            "updatedAt": now,
        },
        upsert=True,
    )
    metadata_updates: dict[str, Any] = {
        "metadata.extractedPageCount": extracted.pageCount,
        "metadata.extractionStatus": "completed",
        "metadata.extractionMethod": extracted.extractionMethod,
        "metadata.documentSha256": extracted.sha256,
        "metadata.tableCount": len(extracted.tables),
        "metadata.extractionWarnings": extracted.warnings,
        "metadata.structuredExtractionCollection": EXTRACTION_COLLECTION,
        "metadata.structureCollection": STRUCTURE_COLLECTION,
        "metadata.structureNodeCount": sum(
            1 for chunk in chunks if (chunk.get("metadata") or {}).get("hierarchyPath")
        ),
        "metadata.repealedChunkCount": sum(
            1
            for chunk in chunks
            if (chunk.get("metadata") or {}).get("amendmentStatus") == "repealed"
        ),
        "metadata.crossReferenceCount": sum(
            len((chunk.get("metadata") or {}).get("crossReferences") or [])
            for chunk in chunks
        ),
        "rawText": extracted.rawText,
        "sha256Hash": extracted.sha256,
        "extractionMethod": extracted.extractionMethod,
        "updatedAt": now,
    }
    if uploaded_file:
        metadata_updates["metadata.uploadedFile"] = uploaded_file
    await database[SOURCE_COLLECTION].update_one(
        {"_id": source["_id"]},
        {"$set": metadata_updates},
    )
    return {
        "source": json_safe(await get_source(source_id)),
        "chunkCount": len(documents),
        "sha256Hash": extracted.sha256,
        "extractedLegalMetadata": {
            "pageCount": extracted.pageCount,
            "tableCount": len(extracted.tables),
            "extractionMethod": extracted.extractionMethod,
        },
        "ingestionStatus": "embedded",
    }


async def ingest_text(
    source_id: str,
    content: str,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    source = await get_source(source_id)
    sha256 = hashlib.sha256(content.encode()).hexdigest()
    if expected_sha256 and expected_sha256.lower() != sha256:
        raise HTTPException(status.HTTP_409_CONFLICT, "Content SHA-256 does not match")
    chunks = chunk_plain_text(content, source)
    documents = await _replace_chunks(source, chunks, extraction_method="manual")
    await get_database()[SOURCE_COLLECTION].update_one(
        {"_id": source["_id"]},
        {
            "$set": {
                "rawText": content,
                "sha256Hash": sha256,
                "extractionMethod": "manual",
                "metadata.extractionMethod": "manual",
                "metadata.extractionStatus": "completed",
                "updatedAt": _now(),
            }
        },
    )
    return {
        "source": json_safe(await get_source(source_id)),
        "chunkCount": len(documents),
        "sha256Hash": sha256,
        "ingestionStatus": "embedded",
    }


async def upload_and_ingest(source_id: str, upload: UploadFile) -> dict[str, Any]:
    data = await upload.read()
    if len(data) > get_settings().MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "Document exceeds upload limit",
        )
    file_name = upload.filename or "document.pdf"
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The AI agent currently accepts PDF documents for structured extraction",
        )
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file_name).name)
    storage_key = f"{source_id}/{hashlib.sha256(data).hexdigest()[:16]}-{safe_name}"
    path = get_settings().KNOWLEDGE_STORAGE_PATH / storage_key
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, data)
    uploaded_file = {
        "originalFileName": file_name,
        "mimeType": upload.content_type or mimetypes.guess_type(file_name)[0] or "application/pdf",
        "fileSizeBytes": len(data),
        "storageKey": storage_key,
        "uploadedAt": _now().isoformat(),
    }
    extracted = await asyncio.to_thread(extract_pdf, data, file_name)
    return await ingest_extraction(source_id, extracted, uploaded_file=uploaded_file)


async def reindex_source(source_id: str) -> dict[str, Any]:
    source = await get_source(source_id)
    extraction = await get_database()[EXTRACTION_COLLECTION].find_one({"sourceId": source["_id"]})
    if extraction and extraction.get("structured"):
        extracted = ExtractedDocument.model_validate(extraction["structured"])
        return await ingest_extraction(source_id, extracted)
    raw_text = source.get("rawText")
    if raw_text:
        return await ingest_text(source_id, raw_text, source.get("sha256Hash"))
    raise HTTPException(status.HTTP_409_CONFLICT, "Source has no stored content to reindex")


async def list_chunks(source_id: str, page: int, limit: int) -> dict[str, Any]:
    object_id = _object_id(source_id)
    collection = get_database()[CHUNK_COLLECTION]
    total = await collection.count_documents({"sourceId": object_id})
    cursor = (
        collection.find({"sourceId": object_id}, {"embedding": 0})
        .sort("chunkIndex", 1)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    documents = await cursor.to_list(length=limit)
    chunks = []
    for document in json_safe(documents):
        chunks.append(
            {
                "id": document.get("id"),
                "chunkIndex": document.get("chunkIndex"),
                "text": document.get("chunkText"),
                "tokenCount": document.get("tokenCount"),
                "citationLabel": document.get("citationLabel"),
                "citationUrl": document.get("citationUrl"),
                "sectionRef": document.get("sectionRef"),
                "sectionNumber": document.get("sectionNumber"),
                "sectionHeading": document.get("sectionTitle"),
                "metadata": document.get("metadata", {}),
                "createdAt": document.get("createdAt"),
                "updatedAt": document.get("updatedAt"),
            }
        )
    return {
        "page": page,
        "limit": limit,
        "totalCount": total,
        "totalPages": max(1, (total + limit - 1) // limit),
        "chunks": chunks,
    }


async def get_source_artifacts(source_id: str) -> dict[str, Any]:
    source = await get_source(source_id)
    extraction = await get_database()[EXTRACTION_COLLECTION].find_one(
        {"sourceId": source["_id"]},
        {"_id": 0, "rawText": 1, "markdown": 1, "structured": 1, "legalStructure": 1},
    )
    if not extraction:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Structured extraction artifacts were not found",
        )
    return json_safe(extraction)


async def set_approval(source_id: str, actor_id: str, approved: bool, reason: str | None = None):
    update: dict[str, Any] = {"updatedAt": _now()}
    actor = ObjectId(actor_id) if ObjectId.is_valid(actor_id) else None
    if approved:
        current = await get_source(source_id)
        if (
            current.get("sourceCategory") == "official_legal_source"
            and not current.get("legalReviewed")
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Official legal sources require legal review before approval",
            )
        next_refresh = current.get("nextRefreshAt")
        if next_refresh and _as_utc(next_refresh) <= _now():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Knowledge source refresh is expired",
            )
        if current.get("ingestionStatus") != "embedded":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Knowledge source must be fully embedded before approval",
            )
        update.update(
            {
                "status": "approved",
                "approvedBy": actor,
                "approvedAt": _now(),
            }
        )
    else:
        update.update(
            {
                "status": "rejected",
                "rejectedBy": actor,
                "rejectedAt": _now(),
                "rejectionReason": reason,
            }
        )
    document = await get_database()[SOURCE_COLLECTION].find_one_and_update(
        {"_id": _object_id(source_id)},
        {"$set": update},
        return_document=True,
    )
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge source not found")
    return json_safe(document)


async def readiness() -> dict[str, Any]:
    database = get_database()
    sources = database[SOURCE_COLLECTION]
    total = await sources.count_documents(
        {"sourceCategory": {"$in": ["official_legal_source", "official_support_source"]}}
    )
    eligible = await sources.count_documents(
        {
            "sourceCategory": {"$in": ["official_legal_source", "official_support_source"]},
            "status": "approved",
            "legalReviewed": True,
            "active": True,
            "ingestionStatus": {"$in": ["embedded", "partial_index_failed"]},
        }
    )
    health = await pinecone_store.health()
    ocr = ocr_health()
    golden = golden_report_health()
    ready = (
        bool(get_settings().OPENAI_API_KEY)
        and (health.get("reachable") or eligible > 0)
        and (not get_settings().RAG_ENABLE_OCR or bool(ocr.get("ready")))
        and (
            not get_settings().LEGAL_REQUIRE_PRODUCTION_GOLDEN
            or bool(golden.get("ready"))
        )
    )
    return {
        "generatedAt": _now().isoformat(),
        "summary": {
            "readinessStatus": "ready" if ready and eligible else "not_ready",
            "readyForPublicLegalRag": bool(ready and eligible),
            "retrievalConfigurationReady": ready,
            "totalOfficialSources": total,
            "eligibleCitationSources": eligible,
            "eligibleLegalSources": eligible,
            "approvedCurrentSources": eligible,
            "legalReviewedSources": eligible,
            "pendingReviewSources": max(0, total - eligible),
            "expiredRefreshSources": 0,
            "metadataOnlySources": await sources.count_documents(
                {"ingestionStatus": "metadata_only"}
            ),
            "failedIngestionSources": await sources.count_documents({"ingestionStatus": "failed"}),
            "blockedSources": max(0, total - eligible),
        },
        "configuration": {
            "openAiApiKeyConfigured": bool(get_settings().OPENAI_API_KEY),
            "embeddingModel": get_settings().OPENAI_EMBEDDING_MODEL,
            "vectorIndex": {
                "status": "ready" if health.get("reachable") else "unavailable",
                "indexName": get_settings().PINECONE_INDEX_NAME,
                "collectionName": CHUNK_COLLECTION,
                "embeddingField": "embedding",
                "embeddingModel": get_settings().OPENAI_EMBEDDING_MODEL,
                "expectedDimensions": health.get("dimension"),
                "message": (
                    "Pinecone reachable"
                    if health.get("reachable")
                    else "Pinecone unavailable"
                ),
            },
            "retrievalReady": ready,
            "ocr": ocr,
            "legalGolden": golden,
        },
        "coverage": [],
        "blockers": [],
    }
