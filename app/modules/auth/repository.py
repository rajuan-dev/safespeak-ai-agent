from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.config.database import get_database


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class AuthRepository:
    def __init__(self) -> None:
        database = get_database()
        self.users = database["users"]
        self.password_reset_requests = database["passwordresetrequests"]

    async def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.users.find_one({"email": email})

    async def find_user_by_google_or_email(
        self, google_id: str, email: str
    ) -> dict[str, Any] | None:
        return await self.users.find_one({"$or": [{"googleId": google_id}, {"email": email}]})

    async def find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        object_id = _object_id(user_id)
        if not object_id:
            return None
        return await self.users.find_one({"_id": object_id})

    async def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.users.insert_one(document)
        return await self.users.find_one({"_id": result.inserted_id})

    async def update_user(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(user_id)
        if not object_id:
            return None
        next_updates = {**updates, "updatedAt": datetime.now(UTC)}
        return await self.users.find_one_and_update(
            {"_id": object_id},
            {"$set": next_updates},
            return_document=ReturnDocument.AFTER,
        )

    async def unset_refresh_token_hash(self, user_id: str) -> None:
        object_id = _object_id(user_id)
        if not object_id:
            return
        await self.users.update_one(
            {"_id": object_id},
            {
                "$unset": {"refreshTokenHash": ""},
                "$set": {"updatedAt": datetime.now(UTC)},
            },
        )

    async def update_refresh_token_hash(self, user_id: str, refresh_token_hash: str) -> None:
        object_id = _object_id(user_id)
        if not object_id:
            return
        await self.users.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "refreshTokenHash": refresh_token_hash,
                    "lastLoginAt": datetime.now(UTC),
                    "updatedAt": datetime.now(UTC),
                }
            },
        )

    async def expire_active_reset_requests(self, user_id: str, audience: str) -> None:
        object_id = _object_id(user_id)
        if not object_id:
            return
        await self.password_reset_requests.update_many(
            {
                "userId": object_id,
                "audience": audience,
                "usedAt": {"$exists": False},
                "expiresAt": {"$gt": datetime.now(UTC)},
            },
            {
                "$set": {
                    "expiresAt": datetime.now(UTC),
                    "updatedAt": datetime.now(UTC),
                }
            },
        )

    async def create_password_reset_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.password_reset_requests.insert_one(document)
        return await self.password_reset_requests.find_one({"_id": result.inserted_id})

    async def find_password_reset_request(
        self, reset_request_id: str, email: str, audience: str
    ) -> dict[str, Any] | None:
        object_id = _object_id(reset_request_id)
        if not object_id:
            return None
        return await self.password_reset_requests.find_one(
            {"_id": object_id, "email": email, "audience": audience}
        )

    async def update_password_reset_request(
        self, reset_request_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(reset_request_id)
        if not object_id:
            return None
        next_updates = {**updates, "updatedAt": datetime.now(UTC)}
        return await self.password_reset_requests.find_one_and_update(
            {"_id": object_id},
            {"$set": next_updates},
            return_document=ReturnDocument.AFTER,
        )

    async def expire_other_password_reset_requests(
        self, user_id: str, audience: str, keep_request_id: str
    ) -> None:
        object_id = _object_id(user_id)
        keep_object_id = _object_id(keep_request_id)
        if not object_id or not keep_object_id:
            return
        await self.password_reset_requests.update_many(
            {
                "userId": object_id,
                "audience": audience,
                "usedAt": {"$exists": False},
                "_id": {"$ne": keep_object_id},
            },
            {"$set": {"expiresAt": datetime.now(UTC), "updatedAt": datetime.now(UTC)}},
        )


def get_auth_repository() -> AuthRepository:
    return AuthRepository()
