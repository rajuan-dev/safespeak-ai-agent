from typing import Any

from pymongo import ReturnDocument

from app.config.database import get_database


class ProfilesRepository:
    def __init__(self) -> None:
        database = get_database()
        self.collection = database["userprofiles"]
        self.admin_taxonomies = database["admintaxonomies"]
        self.admin_cultural_profiles = database["adminculturalprofiles"]

    async def find_one(self, owner_filter: dict[str, Any]) -> dict[str, Any] | None:
        return await self.collection.find_one(owner_filter)

    async def upsert_one(
        self, owner_filter: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.collection.find_one_and_update(
            owner_filter,
            {
                "$set": payload,
                "$setOnInsert": owner_filter,
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def list_active_language_taxonomies(self) -> list[dict[str, Any]]:
        cursor = self.admin_taxonomies.find(
            {
                "type": "language",
                "deletedAt": {"$exists": False},
                "isActive": True,
            },
            projection={"key": 1, "label": 1, "metadata": 1},
        ).sort("label", 1)
        return await cursor.to_list(length=None)

    async def list_active_culture_taxonomies(self) -> list[dict[str, Any]]:
        cursor = self.admin_taxonomies.find(
            {
                "type": "culture",
                "deletedAt": {"$exists": False},
                "isActive": True,
            },
            projection={"label": 1, "metadata": 1},
        ).sort("label", 1)
        return await cursor.to_list(length=None)

    async def list_managed_profiles(self, community_type: str) -> list[dict[str, Any]]:
        cursor = self.admin_cultural_profiles.find(
            {
                "communityType": community_type,
                "isActive": True,
                "validationStatus": "validated",
                "deletedAt": {"$exists": False},
            },
            projection={"name": 1},
        ).sort("name", 1)
        return await cursor.to_list(length=None)


def get_profiles_repository() -> ProfilesRepository:
    return ProfilesRepository()
