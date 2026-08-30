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


class ScamShieldRepository:
    def __init__(self) -> None:
        database = get_database()
        self.analyses = database["scamshieldanalyses"]
        self.reports = database["reports"]
        self.evidence = database["evidence"]

    async def create_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.analyses.insert_one(document)
        return await self.analyses.find_one({"_id": result.inserted_id})

    async def find_analysis_for_owner(
        self, analysis_id: str, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(analysis_id)
        if not object_id:
            return None
        return await self.analyses.find_one({"_id": object_id, **owner_query(owner)})

    async def update_analysis(
        self, analysis_id: str, owner: dict[str, str | None], updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(analysis_id)
        if not object_id:
            return None
        return await self.analyses.find_one_and_update(
            {"_id": object_id, **owner_query(owner)},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def create_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.reports.insert_one(document)
        return await self.reports.find_one({"_id": result.inserted_id})

    async def find_report_for_owner(
        self, report_id: str | None, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        return await self.reports.find_one({"_id": object_id, **owner_query(owner)})

    async def find_evidence_for_owner(
        self, evidence_id: str | None, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(evidence_id)
        if not object_id:
            return None
        return await self.evidence.find_one({"_id": object_id, **owner_query(owner)})


def get_scamshield_repository() -> ScamShieldRepository:
    return ScamShieldRepository()
