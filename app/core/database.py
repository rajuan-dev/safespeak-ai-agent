from datetime import UTC

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings

_client: AsyncMongoClient | None = None


def get_mongo_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncMongoClient(
            settings.MONGODB_URI,
            appname=settings.APP_NAME,
            tz_aware=True,
            tzinfo=UTC,
        )
    return _client


def get_database() -> AsyncDatabase:
    settings = get_settings()
    client = get_mongo_client()
    if settings.MONGODB_DATABASE:
        return client[settings.MONGODB_DATABASE]
    return client.get_default_database()


async def close_database() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
