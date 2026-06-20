import asyncio
from typing import Any

from pinecone import Pinecone

from app.core.config import get_settings


class PineconeStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = (
            Pinecone(api_key=settings.PINECONE_API_KEY)
            if settings.PINECONE_API_KEY
            else None
        )

    @property
    def configured(self) -> bool:
        return self.client is not None

    def _index(self):
        if not self.client:
            raise RuntimeError("PINECONE_API_KEY is not configured")
        return self.client.Index(self.settings.PINECONE_INDEX_NAME)

    async def upsert(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        vectors = [
            {
                "id": str(chunk["_id"]),
                "values": chunk["embedding"],
                "metadata": {
                    "chunkId": str(chunk["_id"]),
                    "sourceId": str(chunk["sourceId"]),
                    "sourceCategory": chunk.get("sourceCategory", ""),
                    "jurisdiction": chunk.get("jurisdiction", ""),
                    "topic": chunk.get("topic", ""),
                    "sectionNumber": chunk.get("sectionNumber") or "",
                    "legalReviewed": bool(chunk.get("legalReviewed")),
                    "active": bool(chunk.get("active", True)),
                },
            }
            for chunk in chunks
        ]
        index = self._index()
        for start in range(0, len(vectors), 100):
            batch = vectors[start : start + 100]
            await asyncio.to_thread(
                index.upsert,
                vectors=batch,
                namespace=self.settings.PINECONE_NAMESPACE,
            )

    async def query(
        self,
        vector: list[float],
        top_k: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = await asyncio.to_thread(
            self._index().query,
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            namespace=self.settings.PINECONE_NAMESPACE,
            filter=filters or None,
        )
        return [
            {
                "id": match.id,
                "score": float(match.score),
                "metadata": dict(match.metadata or {}),
            }
            for match in result.matches
        ]

    async def delete_source(self, source_id: str) -> None:
        if not self.configured:
            return
        await asyncio.to_thread(
            self._index().delete,
            filter={"sourceId": {"$eq": source_id}},
            namespace=self.settings.PINECONE_NAMESPACE,
        )

    async def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "reachable": False}
        try:
            description = await asyncio.to_thread(
                self.client.describe_index,
                self.settings.PINECONE_INDEX_NAME,
            )
            return {
                "configured": True,
                "indexName": self.settings.PINECONE_INDEX_NAME,
                "namespace": self.settings.PINECONE_NAMESPACE,
                "reachable": True,
                "dimension": getattr(description, "dimension", None),
            }
        except Exception as exc:
            return {
                "configured": True,
                "indexName": self.settings.PINECONE_INDEX_NAME,
                "namespace": self.settings.PINECONE_NAMESPACE,
                "reachable": False,
                "error": str(exc),
            }


pinecone_store = PineconeStore()
