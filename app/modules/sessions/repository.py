import os
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.config.database import get_database
from app.modules.sessions.model import ANONYMOUS_SESSION_TTL_DAYS


class SessionsRepository:
    def __init__(self) -> None:
        self.collection = get_database()["anonymoussessions"]
        self._testing = os.getenv("ENVIRONMENT", "").lower() == "test"

    _test_store: dict[str, dict] = {}

    async def create_anonymous_session(self, payload: dict) -> dict:
        document = {
            **payload,
            "_id": ObjectId(),
            "expiresAt": datetime.now(UTC) + timedelta(days=ANONYMOUS_SESSION_TTL_DAYS),
        }
        if self._testing:
            self._test_store[str(document["_id"])] = document
            return dict(document)
        result = await self.collection.insert_one(document)
        return await self.collection.find_one({"_id": result.inserted_id})

    async def find_by_token_hash(self, session_token_hash: str) -> dict | None:
        if self._testing:
            for document in self._test_store.values():
                if (
                    document.get("sessionTokenHash") == session_token_hash
                    and document.get("expiresAt", datetime.min.replace(tzinfo=UTC))
                    > datetime.now(UTC)
                ):
                    return dict(document)
            return None
        return await self.collection.find_one(
            {
                "sessionTokenHash": session_token_hash,
                "expiresAt": {"$gt": datetime.now(UTC)},
            }
        )

    async def find_by_id(self, session_id: str) -> dict | None:
        if not ObjectId.is_valid(session_id):
            return None
        if self._testing:
            return self._test_store.get(session_id)
        return await self.collection.find_one({"_id": ObjectId(session_id)})

    async def convert_to_user(self, session_id: str, user_id: str) -> dict | None:
        if not ObjectId.is_valid(session_id) or not ObjectId.is_valid(user_id):
            return None
        if self._testing:
            document = self._test_store.get(session_id)
            if not document:
                return None
            document["userId"] = ObjectId(user_id)
            document["isAnonymous"] = False
            self._test_store[session_id] = document
            return dict(document)
        result = await self.collection.find_one_and_update(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "userId": ObjectId(user_id),
                    "isAnonymous": False,
                }
            },
            return_document=True,
        )
        return result
