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


class ReportsRepository:
    def __init__(self) -> None:
        database = get_database()
        self.reports = database["reports"]
        self.report_submissions = database["reportsubmissions"]
        self.destinations = database["admindestinations"]
        self.destination_templates = database["admindestinationtemplates"]
        self.conversation_sessions = database["conversationflowsessions"]
        self.conversation_messages = database["conversationflowmessages"]
        self.conversation_facts = database["conversationflowfacts"]
        self.conversation_triage = database["conversationflowtriages"]
        self.evidence = database["evidence"]
        self.user_profiles = database["userprofiles"]
        self.anonymous_sessions = database["anonymoussessions"]

    async def create_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.reports.insert_one(document)
        return await self.reports.find_one({"_id": result.inserted_id})

    async def list_reports(self, owner: dict[str, str | None]) -> list[dict[str, Any]]:
        query = {**owner_query(owner), "deletedAt": {"$exists": False}}
        cursor = self.reports.find(query).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def find_report_for_owner(
        self, report_id: str, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        return await self.reports.find_one({"_id": object_id, **owner_query(owner)})

    async def update_report(
        self, report_id: str, owner: dict[str, str | None], updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        return await self.reports.find_one_and_update(
            {"_id": object_id, **owner_query(owner)},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def append_report_history(
        self,
        report_id: str,
        owner: dict[str, str | None],
        history_entry: dict[str, Any],
        extra_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        update_doc: dict[str, Any] = {
            "$push": {"statusHistory": history_entry},
            "$set": {"updatedAt": datetime.now(UTC)},
        }
        if extra_updates:
            update_doc["$set"].update(extra_updates)
        return await self.reports.find_one_and_update(
            {"_id": object_id, **owner_query(owner)},
            update_doc,
            return_document=ReturnDocument.AFTER,
        )

    async def create_submission(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.report_submissions.insert_one(document)
        return await self.report_submissions.find_one({"_id": result.inserted_id})

    async def list_submissions_for_report(
        self, report_id: str, owner: dict[str, str | None]
    ) -> list[dict[str, Any]]:
        report_object_id = _object_id(report_id)
        if not report_object_id:
            return []
        query = {
            "reportId": report_object_id,
            **owner_query(owner),
            "deletedAt": {"$exists": False},
        }
        cursor = self.report_submissions.find(query).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def find_submission_by_destination(
        self, report_id: str, owner: dict[str, str | None], destination_id: str
    ) -> dict[str, Any] | None:
        report_object_id = _object_id(report_id)
        destination_object_id = _object_id(destination_id)
        if not report_object_id or not destination_object_id:
            return None
        return await self.report_submissions.find_one(
            {
                "reportId": report_object_id,
                "destinationId": destination_object_id,
                **owner_query(owner),
                "deletedAt": {"$exists": False},
            },
            sort=[("createdAt", -1)],
        )

    async def find_submission_for_owner(
        self, submission_id: str, report_id: str, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(submission_id)
        report_object_id = _object_id(report_id)
        if not object_id or not report_object_id:
            return None
        return await self.report_submissions.find_one(
            {"_id": object_id, "reportId": report_object_id, **owner_query(owner)}
        )

    async def update_submission(
        self,
        submission_id: str,
        report_id: str,
        owner: dict[str, str | None],
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        object_id = _object_id(submission_id)
        report_object_id = _object_id(report_id)
        if not object_id or not report_object_id:
            return None
        return await self.report_submissions.find_one_and_update(
            {"_id": object_id, "reportId": report_object_id, **owner_query(owner)},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def get_profile(self, owner: dict[str, str | None]) -> dict[str, Any] | None:
        return await self.user_profiles.find_one(owner_query(owner))

    async def get_anonymous_session(self, session_id: str | None) -> dict[str, Any] | None:
        object_id = _object_id(session_id)
        if not object_id:
            return None
        return await self.anonymous_sessions.find_one({"_id": object_id})

    async def count_evidence_for_report(
        self, report_id: str, owner: dict[str, str | None]
    ) -> int:
        report_object_id = _object_id(report_id)
        if not report_object_id:
            return 0
        return await self.evidence.count_documents(
            {
                "reportId": report_object_id,
                **owner_query(owner),
                "deletedAt": {"$exists": False},
            }
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

    async def get_destinations(
        self, jurisdiction: str, incident_type: str | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "isActive": True,
            "deletedAt": {"$exists": False},
            "$or": [
                {"jurisdiction": jurisdiction},
                {"jurisdiction": {"$in": ["ALL", "AU", "National"]}},
            ],
        }
        if incident_type:
            query["$or"] = [
                {
                    "$and": [
                        {
                            "$or": [
                                {"jurisdiction": jurisdiction},
                                {"jurisdiction": {"$in": ["ALL", "AU", "National"]}},
                            ]
                        },
                        {
                            "$or": [
                                {"supportedIncidentTypes": {"$exists": False}},
                                {"supportedIncidentTypes": {"$size": 0}},
                                {"supportedIncidentTypes": incident_type},
                            ]
                        },
                    ]
                }
            ]
        cursor = self.destinations.find(query).sort("name", 1)
        return await cursor.to_list(length=None)

    async def get_destination(self, destination_id: str) -> dict[str, Any] | None:
        object_id = _object_id(destination_id)
        if not object_id:
            return None
        return await self.destinations.find_one({"_id": object_id, "deletedAt": {"$exists": False}})

    async def get_template_for_destination(self, destination_id: str) -> dict[str, Any] | None:
        object_id = _object_id(destination_id)
        if not object_id:
            return None
        return await self.destination_templates.find_one(
            {"destinationId": object_id, "deletedAt": {"$exists": False}, "isActive": True}
        )

    async def get_conversation_bundle(
        self, conversation_session_id: str, owner: dict[str, str | None]
    ) -> dict[str, Any] | None:
        object_id = _object_id(conversation_session_id)
        if not object_id:
            return None
        session = await self.conversation_sessions.find_one(
            {"_id": object_id, **owner_query(owner), "deletedAt": {"$exists": False}}
        )
        if not session:
            return None
        messages = await self.conversation_messages.find(
            {"conversationSessionId": object_id, "deletedAt": {"$exists": False}}
        ).sort("createdAt", 1).to_list(length=None)
        facts = await self.conversation_facts.find(
            {"conversationSessionId": object_id, "deletedAt": {"$exists": False}}
        ).to_list(length=None)
        triage = await self.conversation_triage.find_one({"conversationSessionId": object_id})
        return {
            "session": session,
            "messages": messages,
            "facts": facts,
            "triage": triage,
        }


def get_reports_repository() -> ReportsRepository:
    return ReportsRepository()
