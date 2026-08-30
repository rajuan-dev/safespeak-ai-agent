import logging
from collections.abc import Sequence
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import OperationFailure

from app.config.database import get_database

logger = logging.getLogger(__name__)


def _normalize_keys(keys: Any) -> list[tuple[str, int]]:
    if isinstance(keys, str):
        return [(keys, ASCENDING)]
    if isinstance(keys, Sequence):
        normalized: list[tuple[str, int]] = []
        for item in keys:
            if isinstance(item, tuple) and len(item) == 2:
                normalized.append((str(item[0]), int(item[1])))
        return normalized
    return []


def _index_matches(existing: dict[str, Any], keys: Any) -> bool:
    existing_keys = list(dict(existing.get("key", {})).items())
    return existing_keys == _normalize_keys(keys)


async def _ensure_index(
    collection: AsyncCollection,
    keys: Any,
    **options: Any,
) -> None:
    try:
        await collection.create_index(keys, **options)
    except OperationFailure as exc:
        if exc.code != 86:
            raise
        existing_indexes = await (await collection.list_indexes()).to_list(length=None)
        for existing in existing_indexes:
            if _index_matches(existing, keys):
                logger.warning(
                    "Reusing existing index with conflicting generated name",
                    extra={
                        "collection": collection.name,
                        "keys": _normalize_keys(keys),
                        "requested_options": options,
                        "existing_index": existing,
                    },
                )
                return
        raise


async def ensure_all_indexes() -> None:
    database = get_database()

    await _ensure_index(database["users"], "email", unique=True)
    await _ensure_index(database["users"], "role")
    await _ensure_index(database["users"], "status")
    await _ensure_index(database["anonymoussessions"], "token", unique=True)
    await _ensure_index(database["userprofiles"], [("userId", ASCENDING)], unique=True, sparse=True)
    await _ensure_index(database["userprofiles"], [("sessionId", ASCENDING)], unique=True, sparse=True)
    await _ensure_index(database["consents"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["privacyrequests"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["reports"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["reports"], [("sessionId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["reportsubmissions"], [("reportId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["evidence"], [("reportId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["evidenceauditchains"], [("evidenceId", ASCENDING), ("sequence", ASCENDING)], unique=True)
    await _ensure_index(database["conversationflowsessions"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["conversationflowsessions"], [("sessionId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["conversationflowmessages"], [("conversationSessionId", ASCENDING), ("createdAt", ASCENDING)])
    await _ensure_index(database["aiinteractions"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["ragknowledgesources"], [("status", ASCENDING), ("active", ASCENDING)])
    await _ensure_index(database["ragchunks"], [("sourceId", ASCENDING), ("chunkIndex", ASCENDING)], unique=True)
    await _ensure_index(database["scamshieldanalyses"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["supportservices"], [("isPublished", ASCENDING), ("isActive", ASCENDING), ("sortOrder", ASCENDING)])
    await _ensure_index(database["warmreferrals"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["advocateprofiles"], [("key", ASCENDING)], unique=True, sparse=True)
    await _ensure_index(database["advocaterequests"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["helpsupportrequests"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["safetyplans"], [("userId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["admintaxonomies"], [("type", ASCENDING), ("key", ASCENDING)], unique=True)
    await _ensure_index(database["adminculturalprofiles"], [("communityType", ASCENDING), ("validationStatus", ASCENDING), ("isActive", ASCENDING)])
    await _ensure_index(database["admindestinations"], [("type", ASCENDING), ("key", ASCENDING)], unique=True)
    await _ensure_index(database["admindestinationtemplates"], [("destinationType", ASCENDING), ("channel", ASCENDING), ("jurisdiction", ASCENDING), ("isActive", ASCENDING)])
    await _ensure_index(database["auditlogs"], [("actorId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["auditlogs"], [("resourceType", ASCENDING), ("resourceId", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["adminnotificationreads"], [("adminUserId", ASCENDING), ("notificationId", ASCENDING)], unique=True)
    await _ensure_index(database["usernotificationreads"], [("userId", ASCENDING), ("notificationId", ASCENDING)], unique=True)
    await _ensure_index(database["contentpages"], "key", unique=True)
    await _ensure_index(database["contentresources"], [("status", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["mediaassets"], [("status", ASCENDING), ("category", ASCENDING), ("createdAt", DESCENDING)])
    await _ensure_index(database["microeducation"], [("status", ASCENDING), ("categoryId", ASCENDING), ("sortOrder", ASCENDING)])
    await _ensure_index(database["microeducationcategories"], [("status", ASCENDING), ("sortOrder", ASCENDING)])
    await _ensure_index(database["feedback"], [("status", ASCENDING), ("source", ASCENDING), ("createdAt", DESCENDING)])
