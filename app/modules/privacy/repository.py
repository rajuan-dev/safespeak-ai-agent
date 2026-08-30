from typing import Any

from bson import ObjectId

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


class PrivacyRepository:
    def __init__(self) -> None:
        database = get_database()
        self.privacy_requests = database["privacyrequests"]
        self.users = database["users"]
        self.anonymous_sessions = database["anonymoussessions"]
        self.user_profiles = database["userprofiles"]
        self.consent_records = database["consentrecords"]
        self.audit_logs = database["auditlogs"]
        self.collections = {
            "reports": database["reports"],
            "report_submissions": database["reportsubmissions"],
            "evidence": database["evidence"],
            "evidence_audit_chain": database["evidenceauditchains"],
            "ai_interactions": database["aiinteractions"],
            "conversation_sessions": database["conversationflowsessions"],
            "conversation_messages": database["conversationflowmessages"],
            "conversation_facts": database["conversationflowfacts"],
            "conversation_triage": database["conversationflowtriages"],
            "scamshield_analyses": database["scamshieldanalyses"],
            "warm_referrals": database["warmreferrals"],
            "advocate_requests": database["advocaterequests"],
            "help_support_requests": database["helpsupportrequests"],
            "safety_plans": database["safetyplans"],
        }

    async def create_privacy_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        document = {**payload, **owner_query(payload)}
        document.pop("userId", None)
        document.pop("sessionId", None)
        result = await self.privacy_requests.insert_one(document)
        return await self.privacy_requests.find_one({"_id": result.inserted_id})

    async def list_privacy_requests(self, owner: dict[str, str | None]) -> list[dict[str, Any]]:
        query = owner_query(owner)
        cursor = self.privacy_requests.find(query).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def get_privacy_request(
        self, owner: dict[str, str | None], request_id: str
    ) -> dict[str, Any] | None:
        object_id = _object_id(request_id)
        if not object_id:
            return None
        return await self.privacy_requests.find_one({"_id": object_id, **owner_query(owner)})

    async def get_user_for_export(self, user_id: str | None) -> dict[str, Any] | None:
        object_id = _object_id(user_id)
        if not object_id:
            return None
        return await self.users.find_one(
            {"_id": object_id},
            projection={
                "email": 1,
                "fullName": 1,
                "contactNo": 1,
                "avatarUrl": 1,
                "role": 1,
                "status": 1,
                "isEmailVerified": 1,
                "lastLoginAt": 1,
                "createdAt": 1,
                "updatedAt": 1,
            },
        )

    async def get_anonymous_session_for_export(
        self, session_id: str | None
    ) -> dict[str, Any] | None:
        object_id = _object_id(session_id)
        if not object_id:
            return None
        return await self.anonymous_sessions.find_one(
            {"_id": object_id},
            projection={
                "isAnonymous": 1,
                "language": 1,
                "jurisdiction": 1,
                "lga": 1,
                "safetyGateAcceptedAt": 1,
                "expiresAt": 1,
                "createdAt": 1,
                "updatedAt": 1,
            },
        )

    async def get_profile_for_export(self, owner: dict[str, str | None]) -> dict[str, Any] | None:
        return await self.user_profiles.find_one(owner_query(owner))

    async def get_consent_history_for_export(
        self, owner: dict[str, str | None]
    ) -> list[dict[str, Any]]:
        cursor = self.consent_records.find(owner_query(owner)).sort("version", -1)
        return await cursor.to_list(length=None)

    async def get_owner_documents(
        self,
        collection_key: str,
        owner: dict[str, str | None],
        *,
        sort: list[tuple[str, int]] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self.collections[collection_key].find(owner_query(owner))
        if sort:
            cursor = cursor.sort(sort)
        return await cursor.to_list(length=None)

    async def get_audit_logs_for_owner(
        self, owner: dict[str, str | None]
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = (
            {"actorId": _object_id(owner["userId"])}
            if owner.get("userId")
            else {"sessionId": _object_id(owner["sessionId"])}
        )
        cursor = self.audit_logs.find(query).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def get_conversation_children(
        self, session_ids: list[ObjectId], collection_key: str
    ) -> list[dict[str, Any]]:
        if not session_ids:
            return []
        cursor = self.collections[collection_key].find(
            {"conversationSessionId": {"$in": session_ids}}
        )
        if collection_key == "conversation_messages":
            cursor = cursor.sort("createdAt", 1)
        return await cursor.to_list(length=None)


def get_privacy_repository() -> PrivacyRepository:
    return PrivacyRepository()
