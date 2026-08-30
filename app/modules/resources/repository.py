from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.config.database import get_database


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class ResourcesRepository:
    def __init__(self) -> None:
        self.resources = get_database()["resources"]

    async def list_resources(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.resources.find(query).sort([("sortOrder", 1), ("name", 1)])
        return await cursor.to_list(length=None)

    async def create_resource(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.resources.insert_one(document)
        return await self.resources.find_one({"_id": result.inserted_id})

    async def update_resource(self, resource_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(resource_id)
        if not object_id:
            return None
        return await self.resources.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_resource(self, resource_id: str) -> dict[str, Any] | None:
        object_id = _object_id(resource_id)
        if not object_id:
            return None
        return await self.resources.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {"deletedAt": datetime.now(UTC), "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )


def get_resources_repository() -> ResourcesRepository:
    return ResourcesRepository()
