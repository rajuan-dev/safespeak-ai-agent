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


class SupportRepository:
    def __init__(self) -> None:
        database = get_database()
        self.support_services = database["supportservices"]
        self.warm_referrals = database["warmreferrals"]
        self.advocate_profiles = database["advocateprofiles"]
        self.advocate_requests = database["advocaterequests"]
        self.help_support_requests = database["helpsupportrequests"]
        self.safety_plans = database["safetyplans"]
        self.reports = database["reports"]

    async def seed_support_service(self, payload: dict[str, Any]) -> None:
        timestamps = {"createdAt": datetime.now(UTC), "updatedAt": datetime.now(UTC)}
        await self.support_services.update_one(
            {"key": payload["key"]},
            {"$setOnInsert": {**payload, **timestamps}},
            upsert=True,
        )

    async def seed_advocate_profile(self, payload: dict[str, Any]) -> None:
        timestamps = {"createdAt": datetime.now(UTC), "updatedAt": datetime.now(UTC)}
        await self.advocate_profiles.update_one(
            {"key": payload["key"]},
            {"$setOnInsert": {**payload, **timestamps}},
            upsert=True,
        )

    async def list_support_services(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.support_services.find(query).sort([("sortOrder", 1), ("name", 1)])
        return await cursor.to_list(length=None)

    async def find_support_service(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return await self.support_services.find_one(query)

    async def list_advocate_profiles(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.advocate_profiles.find(query).sort("displayName", 1)
        return await cursor.to_list(length=None)

    async def find_advocate_profile(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return await self.advocate_profiles.find_one(query)

    async def find_duplicate_advocate_request(
        self, owner: dict[str, str | None], advocate_profile_id: ObjectId, statuses: list[str]
    ) -> dict[str, Any] | None:
        return await self.advocate_requests.find_one(
            {
                **owner_query(owner),
                "advocateProfileId": advocate_profile_id,
                "status": {"$in": statuses},
            },
            sort=[("createdAt", -1)],
        )

    async def create_warm_referral(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.warm_referrals.insert_one(document)
        return await self.warm_referrals.find_one({"_id": result.inserted_id})

    async def create_advocate_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.advocate_requests.insert_one(document)
        return await self.advocate_requests.find_one({"_id": result.inserted_id})

    async def list_owned_advocate_requests(
        self, owner: dict[str, str | None], query: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        cursor = (
            self.advocate_requests.find({**owner_query(owner), **query})
            .sort("createdAt", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=None)

    async def find_owned_advocate_request(
        self, owner: dict[str, str | None], request_id: str
    ) -> dict[str, Any] | None:
        object_id = _object_id(request_id)
        if not object_id:
            return None
        return await self.advocate_requests.find_one({"_id": object_id, **owner_query(owner)})

    async def update_owned_advocate_request(
        self, owner: dict[str, str | None], request_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(request_id)
        if not object_id:
            return None
        return await self.advocate_requests.find_one_and_update(
            {"_id": object_id, **owner_query(owner)},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def create_help_support_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.help_support_requests.insert_one(document)
        return await self.help_support_requests.find_one({"_id": result.inserted_id})

    async def list_safety_plans(self, owner: dict[str, str | None]) -> list[dict[str, Any]]:
        cursor = self.safety_plans.find(owner_query(owner)).sort("createdAt", -1)
        return await cursor.to_list(length=None)

    async def create_safety_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {**payload, "createdAt": now, "updatedAt": now}
        result = await self.safety_plans.insert_one(document)
        return await self.safety_plans.find_one({"_id": result.inserted_id})

    async def update_safety_plan(
        self, owner: dict[str, str | None], safety_plan_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        object_id = _object_id(safety_plan_id)
        if not object_id:
            return None
        return await self.safety_plans.find_one_and_update(
            {"_id": object_id, **owner_query(owner)},
            {"$set": {**updates, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )

    async def find_report_for_owner(
        self, owner: dict[str, str | None], report_id: str | None
    ) -> dict[str, Any] | None:
        object_id = _object_id(report_id)
        if not object_id:
            return None
        return await self.reports.find_one({"_id": object_id, **owner_query(owner)})


def get_support_repository() -> SupportRepository:
    return SupportRepository()
