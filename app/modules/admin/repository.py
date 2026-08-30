from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.config.database import get_database


def _object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class AdminRepository:
    def __init__(self) -> None:
        database = get_database()
        self.users = database["users"]
        self.privacy_requests = database["privacyrequests"]
        self.destinations = database["admindestinations"]
        self.templates = database["admindestinationtemplates"]
        self.rag_sources = database["ragknowledgesources"]
        self.content_resources = database["contentresources"]
        self.microeducation = database["microeducation"]
        self.report_submissions = database["reportsubmissions"]
        self.support_services = database["supportservices"]
        self.warm_referrals = database["warmreferrals"]
        self.audit_logs = database["auditlogs"]
        self.ai_interactions = database["aiinteractions"]
        self.reports = database["reports"]
        self.admin_notification_reads = database["adminnotificationreads"]

    async def count_documents(self, collection_name: str, query: dict[str, Any]) -> int:
        return await getattr(self, collection_name).count_documents(query)

    async def list_users(self, query: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        cursor = self.users.find(query).sort("createdAt", -1).limit(limit)
        return await cursor.to_list(length=None)

    async def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.users.insert_one(document)
        return await self.users.find_one({"_id": result.inserted_id})

    async def update_user(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(user_id)
        if not object_id:
            return None
        return await self.users.find_one_and_update(
            {"_id": object_id},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_privacy_requests(self, query: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        cursor = self.privacy_requests.find(query).sort("createdAt", -1).limit(limit)
        return await cursor.to_list(length=None)

    async def update_privacy_request(self, request_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(request_id)
        if not object_id:
            return None
        return await self.privacy_requests.find_one_and_update(
            {"_id": object_id},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_destinations(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.destinations.find(query).sort("name", 1)
        return await cursor.to_list(length=None)

    async def create_destination(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.destinations.insert_one(document)
        return await self.destinations.find_one({"_id": result.inserted_id})

    async def update_destination(self, destination_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(destination_id)
        if not object_id:
            return None
        return await self.destinations.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_templates(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.templates.find(query).sort("name", 1)
        return await cursor.to_list(length=None)

    async def create_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.templates.insert_one(document)
        return await self.templates.find_one({"_id": result.inserted_id})

    async def update_template(self, template_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(template_id)
        if not object_id:
            return None
        return await self.templates.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_report_deliveries(self, query: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        cursor = self.report_submissions.find(query).sort("createdAt", -1).limit(limit)
        return await cursor.to_list(length=None)

    async def list_knowledge_sources(self) -> list[dict[str, Any]]:
        cursor = self.rag_sources.find({"deletedAt": {"$exists": False}}).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def list_educational_content(self) -> dict[str, list[dict[str, Any]]]:
        content_resources = await self.content_resources.find({"deletedAt": {"$exists": False}}).sort("createdAt", -1).to_list(length=None)
        microeducation = await self.microeducation.find({"deletedAt": {"$exists": False}}).sort("createdAt", -1).to_list(length=None)
        return {"resources": content_resources, "microeducation": microeducation}

    async def list_support_services(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.support_services.find(query).sort([("sortOrder", 1), ("name", 1)])
        return await cursor.to_list(length=None)

    async def create_support_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.support_services.insert_one(document)
        return await self.support_services.find_one({"_id": result.inserted_id})

    async def update_support_service(self, service_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(service_id)
        if not object_id:
            return None
        return await self.support_services.find_one_and_update(
            {"_id": object_id, "deletedAt": {"$exists": False}},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_support_service(self, service_id: str) -> dict[str, Any] | None:
        return await self.update_support_service(service_id, {"deletedAt": datetime.now(UTC)})

    async def list_warm_referrals(self, query: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        cursor = self.warm_referrals.find(query).sort("createdAt", -1).limit(limit)
        return await cursor.to_list(length=None)

    async def update_warm_referral(self, referral_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        object_id = _object_id(referral_id)
        if not object_id:
            return None
        return await self.warm_referrals.find_one_and_update(
            {"_id": object_id},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_recent_audit_logs(self, limit: int) -> list[dict[str, Any]]:
        cursor = self.audit_logs.find({}).sort("createdAt", -1).limit(limit)
        return await cursor.to_list(length=None)

    async def find_notification_read(self, admin_user_id: str, notification_id: str) -> dict[str, Any] | None:
        return await self.admin_notification_reads.find_one({"adminUserId": admin_user_id, "notificationId": notification_id})

    async def mark_notification_read(self, admin_user_id: str, notification_id: str) -> dict[str, Any]:
        await self.admin_notification_reads.update_one(
            {"adminUserId": admin_user_id, "notificationId": notification_id},
            {"$set": {"adminUserId": admin_user_id, "notificationId": notification_id, "readAt": datetime.now(UTC)}},
            upsert=True,
        )
        return await self.admin_notification_reads.find_one({"adminUserId": admin_user_id, "notificationId": notification_id})

    async def mark_notifications_read_all(self, admin_user_id: str, notification_ids: list[str]) -> int:
        count = 0
        for notification_id in notification_ids:
            await self.mark_notification_read(admin_user_id, notification_id)
            count += 1
        return count


def get_admin_repository() -> AdminRepository:
    return AdminRepository()
