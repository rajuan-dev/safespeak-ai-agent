from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.config.database import get_database


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def owner_query(owner: dict[str, str | None]) -> dict[str, ObjectId]:
    if owner.get("userId"):
        object_id = _object_id(owner["userId"])
        if object_id:
            return {"userId": object_id}
    if owner.get("sessionId"):
        object_id = _object_id(owner["sessionId"])
        if object_id:
            return {"sessionId": object_id}
    return {}


class ConversationFlowRepository:
    def __init__(self) -> None:
        database = get_database()
        self.sessions = database["conversationflowsessions"]
        self.messages = database["conversationflowmessages"]
        self.facts = database["conversationflowfacts"]
        self.triage = database["conversationflowtriages"]

    async def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, **owner_query(payload), "createdAt": now, "updatedAt": now}
        document.pop("userId", None)
        document.pop("sessionId", None)
        result = await self.sessions.insert_one(document)
        return await self.sessions.find_one({"_id": result.inserted_id})

    async def find_session_for_owner(
        self, session_id: str, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(session_id)
        if not object_id:
            return None
        return await self.sessions.find_one({"_id": object_id, **owner_query(owner)})

    async def update_session(
        self, session_id: str, owner: dict[str, str | None], updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(session_id)
        if not object_id:
            return None
        return await self.sessions.find_one_and_update(
            {"_id": object_id, **owner_query(owner)},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def create_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.messages.insert_one(document)
        return await self.messages.find_one({"_id": result.inserted_id})

    async def list_messages(self, conversation_session_id: str) -> list[dict[str, Any]]:
        object_id = _object_id(conversation_session_id)
        if not object_id:
            return []
        cursor = self.messages.find({"conversationSessionId": object_id}).sort("turnNumber", 1)
        return await cursor.to_list(length=None)

    async def get_facts(self, conversation_session_id: str) -> dict[str, Any] | None:
        object_id = _object_id(conversation_session_id)
        if not object_id:
            return None
        return await self.facts.find_one({"conversationSessionId": object_id})

    async def upsert_facts(
        self, conversation_session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(conversation_session_id)
        if not object_id:
            return None
        return await self.facts.find_one_and_update(
            {"conversationSessionId": object_id},
            {
                "$set": {**payload, "updatedAt": datetime.now(UTC)},
                "$setOnInsert": {"createdAt": datetime.now(UTC)},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def get_triage(self, conversation_session_id: str) -> dict[str, Any] | None:
        object_id = _object_id(conversation_session_id)
        if not object_id:
            return None
        return await self.triage.find_one({"conversationSessionId": object_id})

    async def upsert_triage(
        self, conversation_session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(conversation_session_id)
        if not object_id:
            return None
        return await self.triage.find_one_and_update(
            {"conversationSessionId": object_id},
            {
                "$set": {**payload, "updatedAt": datetime.now(UTC)},
                "$setOnInsert": {"createdAt": datetime.now(UTC)},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )


def get_conversation_flow_repository() -> ConversationFlowRepository:
    return ConversationFlowRepository()
