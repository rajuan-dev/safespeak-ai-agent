from datetime import UTC, datetime
from typing import Any

from pymongo import ReturnDocument

from app.config.database import get_database

from .model import DEFAULT_PLATFORM_SETTINGS, PLATFORM_SETTINGS_KEY


class PlatformSettingsRepository:
    def __init__(self) -> None:
        self.platform_settings = get_database()["platformsettings"]

    async def get_or_create(self) -> dict[str, Any]:
        document = await self.platform_settings.find_one({"key": PLATFORM_SETTINGS_KEY})
        if document:
            return document
        now = datetime.now(UTC)
        payload = {
            "key": PLATFORM_SETTINGS_KEY,
            "draft": DEFAULT_PLATFORM_SETTINGS,
            "published": DEFAULT_PLATFORM_SETTINGS,
            "version": 1,
            "createdAt": now,
            "updatedAt": now,
        }
        await self.platform_settings.insert_one(payload)
        return await self.platform_settings.find_one({"key": PLATFORM_SETTINGS_KEY})

    async def update_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.platform_settings.find_one_and_update(
            {"key": PLATFORM_SETTINGS_KEY},
            {"$set": {**payload, "updatedAt": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
            upsert=True,
        )

    async def publish(self, published_payload: dict[str, Any], published_by: str | None) -> dict[str, Any]:
        await self.get_or_create()
        return await self.platform_settings.find_one_and_update(
            {"key": PLATFORM_SETTINGS_KEY},
            {
                "$set": {
                    "published": published_payload,
                    "publishedAt": datetime.now(UTC),
                    "publishedBy": published_by,
                    "updatedAt": datetime.now(UTC),
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )


def get_platform_settings_repository() -> PlatformSettingsRepository:
    return PlatformSettingsRepository()
