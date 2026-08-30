from typing import Any

from bson import ObjectId

from app.core.database import get_database
from app.services.knowledge import (
    CHUNK_COLLECTION,
    EXTRACTION_COLLECTION,
    SOURCE_COLLECTION,
    STRUCTURE_COLLECTION,
)
from app.services.vector_store import pinecone_store


def _object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid ObjectId")
    return ObjectId(value)


class RagRepository:
    def __init__(self) -> None:
        database = get_database()
        self.sources = database[SOURCE_COLLECTION]
        self.chunks = database[CHUNK_COLLECTION]
        self.extractions = database[EXTRACTION_COLLECTION]
        self.structures = database[STRUCTURE_COLLECTION]

    async def get_source(self, source_id: str) -> dict[str, Any] | None:
        return await self.sources.find_one(
            {"_id": _object_id(source_id), "deletedAt": {"$exists": False}}
        )

    async def get_extraction(self, source_id: str) -> dict[str, Any] | None:
        return await self.extractions.find_one({"sourceId": _object_id(source_id)})

    async def update_source(self, source_id: str, fields: dict[str, Any]) -> None:
        await self.sources.update_one({"_id": _object_id(source_id)}, {"$set": fields})

    async def pinecone_health(self) -> dict[str, Any]:
        return await pinecone_store.health()


def get_rag_repository() -> RagRepository:
    return RagRepository()
