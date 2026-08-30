import pytest
from fastapi import HTTPException

from app.modules.rag import governance as rag_governance_module
from app.modules.rag import service as rag_service_module
from app.modules.rag.schema import (
    ApproveOcrKnowledgeSourceInput,
    KnowledgeIngestInput,
    KnowledgeRefreshInput,
)


class FakeRagRepository:
    def __init__(self, *, has_extraction: bool = True):
        self.source = {
            "_id": "507f1f77bcf86cd799439211",
            "metadata": {"extractedPageCount": 2, "uploadedFile": {}},
            "status": "pending_review",
            "legalReviewed": False,
            "updatedAt": "2026-07-21T00:00:00+00:00",
            "rawText": "Example text",
            "localFilePath": "C:/tmp/example.pdf",
            "extractionMethod": "pymupdf_ocr",
        }
        self.extraction = (
            {
                "structured": {
                    "pages": [
                        {
                            "number": 1,
                            "text": "Page 1",
                            "ocrUsed": True,
                            "ocrConfidence": 0.95,
                        },
                        {
                            "number": 2,
                            "text": "Page 2",
                            "ocrUsed": True,
                            "ocrConfidence": 0.96,
                        },
                    ]
                }
            }
            if has_extraction
            else None
        )
        self.updated = None

    async def get_source(self, source_id):
        return self.source | {"_id": source_id}

    async def get_extraction(self, source_id):
        return self.extraction

    async def update_source(self, source_id, fields):
        self.updated = (source_id, fields)

    async def pinecone_health(self):
        return {"configured": True, "reachable": True}


async def test_ingest_service_uses_direct_content(monkeypatch):
    async def fake_ingest_text(source_id, content, expected_sha256):
        return {"source": {"id": source_id}, "chunkCount": 3, "content": content}

    monkeypatch.setattr(rag_service_module, "legacy_ingest_text", fake_ingest_text)
    result = await rag_service_module.ingest_knowledge_source(
        "507f1f77bcf86cd799439211",
        KnowledgeIngestInput(content="policy text"),
    )
    assert result["chunkCount"] == 3


async def test_refresh_service_falls_back_to_reindex(monkeypatch):
    async def fake_reindex(source_id):
        return {"source": {"id": source_id}, "chunkCount": 2}

    monkeypatch.setattr(rag_service_module, "legacy_reindex_source", fake_reindex)
    result = await rag_service_module.refresh_knowledge_source(
        "507f1f77bcf86cd799439211",
        KnowledgeRefreshInput(),
    )
    assert result["chunkCount"] == 2


async def test_ocr_preview_returns_paged_output():
    preview = await rag_governance_module.get_knowledge_source_ocr_preview(
        "507f1f77bcf86cd799439211",
        page=1,
        page_size=1,
        repository=FakeRagRepository(),
    )
    assert preview["totalCount"] == 2
    assert preview["pages"][0]["ocrUsed"] is True


async def test_approve_ocr_requires_extraction():
    with pytest.raises(HTTPException):
        await rag_governance_module.approve_ocr_knowledge_source(
            "507f1f77bcf86cd799439211",
            "507f1f77bcf86cd799439012",
            legal_reviewed=ApproveOcrKnowledgeSourceInput().legalReviewed,
            repository=FakeRagRepository(has_extraction=False),
        )
