import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.config.database import get_database

from .prompts import DEFAULT_PLATFORM_SETTINGS


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def owner_query(principal: Any) -> dict[str, ObjectId]:
    if getattr(principal, "user_id", None):
        object_id = _object_id(principal.user_id)
        if object_id:
            return {"userId": object_id}
    if getattr(principal, "session_id", None):
        object_id = _object_id(principal.session_id)
        if object_id:
            return {"sessionId": object_id}
    return {}


class AiRepository:
    def __init__(self) -> None:
        database = get_database()
        self.reports = database["reports"]
        self.evidence = database["evidences"]
        self.platform_settings = database["platformsettings"]
        self.ai_interactions = database["aiinteractions"]

    async def find_owned_report(
        self, principal: Any, report_id: str | None
    ) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        return await self.reports.find_one(
            {"_id": object_id, **owner_query(principal), "deletedAt": {"$exists": False}}
        )

    async def list_report_evidence(
        self, principal: Any, report_id: ObjectId
    ) -> list[dict[str, Any]]:
        cursor = self.evidence.find(
            {
                "reportId": report_id,
                **owner_query(principal),
                "deletedAt": {"$exists": False},
            },
            {
                "_id": 1,
                "fileName": 1,
                "mimeType": 1,
                "sha256Hash": 1,
                "status": 1,
            },
        )
        return await cursor.to_list(length=None)

    async def get_public_platform_settings(self) -> dict[str, Any]:
        settings = await self.platform_settings.find_one({"key": "default"})
        if not settings:
            return deepcopy(DEFAULT_PLATFORM_SETTINGS)
        published = settings.get("published") or {}
        return {
            "ai": {
                **DEFAULT_PLATFORM_SETTINGS["ai"],
                **published.get("ai", {}),
            },
            "version": settings.get("version") or 1,
        }

    async def create_ai_interaction(
        self,
        *,
        principal: Any | None,
        action: str,
        model: str,
        language: str | None,
        request_payload: dict[str, Any],
        output_payload: dict[str, Any],
        guardrails: dict[str, Any],
        review_status: str,
        citations: list[dict[str, Any]] | None = None,
        report_id: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        request_blob = repr(request_payload)
        document: dict[str, Any] = {
            "action": action,
            "model": model,
            "language": language,
            "inputHash": hashlib.sha256(request_blob.encode("utf-8")).hexdigest(),
            "requestPayload": request_payload,
            "output": output_payload,
            "citations": citations or [],
            "guardrails": guardrails,
            "reviewStatus": review_status,
            "error": error,
            "createdAt": now,
            "updatedAt": now,
        }
        if principal and getattr(principal, "user_id", None):
            user_id = _object_id(principal.user_id)
            if user_id:
                document["userId"] = user_id
        if principal and getattr(principal, "session_id", None):
            session_id = _object_id(principal.session_id)
            if session_id:
                document["sessionId"] = session_id
        if report_id:
            report_object_id = _object_id(report_id)
            if report_object_id:
                document["reportId"] = report_object_id
        result = await self.ai_interactions.insert_one(document)
        return await self.ai_interactions.find_one({"_id": result.inserted_id})

    async def find_owned_evidence(
        self, principal: Any, evidence_id: str | None
    ) -> dict[str, Any] | None:
        object_id = _object_id(evidence_id)
        if not object_id:
            return None
        return await self.evidence.find_one(
            {"_id": object_id, **owner_query(principal), "deletedAt": {"$exists": False}}
        )

    async def update_evidence_transcription(
        self, evidence_id: ObjectId, payload: dict[str, Any]
    ) -> None:
        await self.evidence.update_one({"_id": evidence_id}, {"$set": {"transcription": payload}})

    async def update_report_narrative(self, report_id: ObjectId, transcript: str) -> None:
        await self.reports.update_one(
            {"_id": report_id}, {"$set": {"originalNarrative": transcript}}
        )

    async def update_report_structured_fields(
        self, report_id: ObjectId, structured_fields: dict[str, Any]
    ) -> None:
        await self.reports.update_one(
            {"_id": report_id}, {"$set": {"structuredFields": structured_fields}}
        )


def get_ai_repository() -> AiRepository:
    return AiRepository()
