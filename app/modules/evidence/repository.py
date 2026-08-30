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


class EvidenceRepository:
    def __init__(self) -> None:
        database = get_database()
        self.evidence = database["evidence"]
        self.evidence_audit_chain = database["evidenceauditchains"]
        self.reports = database["reports"]

    async def create_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.evidence.insert_one(document)
        return await self.evidence.find_one({"_id": result.inserted_id})

    async def find_evidence_for_owner(
        self, evidence_id: str, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(evidence_id)
        if not object_id:
            return None
        return await self.evidence.find_one({"_id": object_id, **owner_query(owner)})

    async def update_evidence(
        self, evidence_id: str, owner: dict[str, str | None], updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(evidence_id)
        if not object_id:
            return None
        return await self.evidence.find_one_and_update(
            {"_id": object_id, **owner_query(owner)},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_evidence_for_report(
        self, report_id: str, owner: dict[str, str | None]
    ) -> list[dict[str, Any]]:
        report_object_id = _object_id(report_id)
        if not report_object_id:
            return []
        cursor = self.evidence.find(
            {
                "reportId": report_object_id,
                **owner_query(owner),
                "deletedAt": {"$exists": False},
            }
        ).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def find_report_for_owner(
        self, report_id: str, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        return await self.reports.find_one(
            {"_id": object_id, **owner_query(owner), "deletedAt": {"$exists": False}}
        )

    async def update_report(self, report_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        return await self.reports.find_one_and_update(
            {"_id": object_id},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def latest_audit_record(self, evidence_id: str) -> dict[str, Any] | None:
        object_id = _object_id(evidence_id)
        if not object_id:
            return None
        return await self.evidence_audit_chain.find_one(
            {"evidenceId": object_id}, sort=[("sequence", -1)]
        )

    async def create_audit_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self.evidence_audit_chain.insert_one(payload)
        return await self.evidence_audit_chain.find_one({"_id": result.inserted_id})

    async def list_audit_chain(self, evidence_id: str) -> list[dict[str, Any]]:
        object_id = _object_id(evidence_id)
        if not object_id:
            return []
        cursor = self.evidence_audit_chain.find({"evidenceId": object_id}).sort("sequence", 1)
        return await cursor.to_list(length=None)


def get_evidence_repository() -> EvidenceRepository:
    return EvidenceRepository()
