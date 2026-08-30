from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.config.database import get_database


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class TaxonomyRepository:
    def __init__(self) -> None:
        database = get_database()
        self.taxonomies = database["admintaxonomies"]
        self.reports = database["reports"]

    async def list_taxonomies(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.taxonomies.find(query).sort([("type", 1), ("label", 1)])
        return await cursor.to_list(length=None)

    async def get_taxonomy(self, taxonomy_id: str) -> dict[str, Any] | None:
        object_id = _object_id(taxonomy_id)
        if not object_id:
            return None
        return await self.taxonomies.find_one({"_id": object_id, "deletedAt": {"$exists": False}})

    async def create_taxonomy(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.taxonomies.insert_one(document)
        return await self.taxonomies.find_one({"_id": result.inserted_id})

    async def update_taxonomy(self, taxonomy_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(taxonomy_id)
        if not object_id:
            return None
        return await self.taxonomies.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_taxonomy(self, taxonomy_id: str) -> dict[str, Any] | None:
        object_id = _object_id(taxonomy_id)
        if not object_id:
            return None
        return await self.taxonomies.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {"deletedAt": datetime.now(UTC), "updatedAt": datetime.now(UTC), "isActive": False}},
            return_document=ReturnDocument.AFTER,
        )

    async def count_reports_using_taxonomy(self, taxonomy: dict[str, Any]) -> int:
        key = taxonomy.get("key")
        label = taxonomy.get("label")
        return await self.reports.count_documents(
            {
                "deletedAt": {"$exists": False},
                "$or": [
                    {"incidentType": key},
                    {"incidentType": label},
                    {"supportNeed": key},
                    {"supportNeed": label},
                    {"language": key},
                    {"language": label},
                ],
            }
        )


def get_taxonomy_repository() -> TaxonomyRepository:
    return TaxonomyRepository()
