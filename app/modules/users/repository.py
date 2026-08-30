from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.config.database import get_database


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class UsersRepository:
    def __init__(self) -> None:
        self.collection = get_database()["users"]

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        object_id = _object_id(user_id)
        if not object_id:
            return None
        return await self.collection.find_one({"_id": object_id})

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"email": email})

    async def update_by_id(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(user_id)
        if not object_id:
            return None
        return await self.collection.find_one_and_update(
            {"_id": object_id},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def soft_delete_by_id(self, user_id: str) -> dict[str, Any] | None:
        object_id = _object_id(user_id)
        if not object_id:
            return None
        now = datetime.now(UTC)
        return await self.collection.find_one_and_update(
            {"_id": object_id},
            {"$set": {"status": "deleted", "deletedAt": now, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )


def get_users_repository() -> UsersRepository:
    return UsersRepository()
