from typing import Any

from bson import ObjectId

from app.config.database import get_database


def _owner_query(owner: dict[str, str | None]) -> dict[str, ObjectId]:
    if owner.get("userId") and ObjectId.is_valid(owner["userId"]):
        return {"userId": ObjectId(owner["userId"])}
    if owner.get("sessionId") and ObjectId.is_valid(owner["sessionId"]):
        return {"sessionId": ObjectId(owner["sessionId"])}
    return {}


class ConsentRepository:
    def __init__(self) -> None:
        self.collection = get_database()["consentrecords"]

    async def find_latest(self, owner: dict[str, str | None]) -> dict[str, Any] | None:
        query = _owner_query(owner)
        if not query:
            return None
        return await self.collection.find_one(query, sort=[("version", -1)])

    async def find_history(self, owner: dict[str, str | None]) -> list[dict[str, Any]]:
        query = _owner_query(owner)
        if not query:
            return []
        cursor = self.collection.find(query).sort("version", -1)
        return await cursor.to_list(length=None)

    async def create_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        document = dict(payload)
        document.pop("userId", None)
        document.pop("sessionId", None)
        document.update(_owner_query(payload))
        result = await self.collection.insert_one(document)
        return await self.collection.find_one({"_id": result.inserted_id})


def get_consent_repository() -> ConsentRepository:
    return ConsentRepository()
