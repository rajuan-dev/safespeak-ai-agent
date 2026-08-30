from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.config.database import get_database


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class ContentRepository:
    def __init__(self) -> None:
        database = get_database()
        self.content_resources = database["contentresources"]
        self.microeducation = database["microeducation"]
        self.microeducation_categories = database["microeducationcategories"]

    async def list_content_resources(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.content_resources.find(query).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def get_content_resource(self, resource_id: str) -> dict[str, Any] | None:
        object_id = _object_id(resource_id)
        if not object_id:
            return None
        return await self.content_resources.find_one({"_id": object_id, "deletedAt": {"$exists": False}})

    async def create_content_resource(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.content_resources.insert_one(document)
        return await self.content_resources.find_one({"_id": result.inserted_id})

    async def update_content_resource(self, resource_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(resource_id)
        if not object_id:
            return None
        return await self.content_resources.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_content_resource(self, resource_id: str) -> dict[str, Any] | None:
        return await self.update_content_resource(resource_id, {"deletedAt": datetime.now(UTC)})

    async def list_microeducation(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.microeducation.find(query).sort([("sortOrder", 1), ("createdAt", -1)])
        return await cursor.to_list(length=None)

    async def get_microeducation(self, item_id: str) -> dict[str, Any] | None:
        object_id = _object_id(item_id)
        if not object_id:
            return None
        return await self.microeducation.find_one({"_id": object_id, "deletedAt": {"$exists": False}})

    async def create_microeducation(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.microeducation.insert_one(document)
        return await self.microeducation.find_one({"_id": result.inserted_id})

    async def update_microeducation(self, item_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(item_id)
        if not object_id:
            return None
        return await self.microeducation.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_microeducation(self, item_id: str) -> dict[str, Any] | None:
        return await self.update_microeducation(item_id, {"deletedAt": datetime.now(UTC)})

    async def list_microeducation_categories(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.microeducation_categories.find(query).sort([("sortOrder", 1), ("name", 1)])
        return await cursor.to_list(length=None)

    async def get_microeducation_category(self, category_id: str) -> dict[str, Any] | None:
        object_id = _object_id(category_id)
        if not object_id:
            return None
        return await self.microeducation_categories.find_one({"_id": object_id, "deletedAt": {"$exists": False}})

    async def create_microeducation_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.microeducation_categories.insert_one(document)
        return await self.microeducation_categories.find_one({"_id": result.inserted_id})

    async def update_microeducation_category(self, category_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(category_id)
        if not object_id:
            return None
        return await self.microeducation_categories.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_microeducation_category(self, category_id: str) -> dict[str, Any] | None:
        return await self.update_microeducation_category(category_id, {"deletedAt": datetime.now(UTC)})


def get_content_repository() -> ContentRepository:
    return ContentRepository()
