import hashlib
import os
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.config.database import get_database

from .repository import AuditRepository, get_audit_repository
from .schema import AuditLogsQueryInput


def _hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _to_object_id(value: str | None) -> ObjectId | None:
    if value and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


async def create_audit_log(
    *,
    actor_type: str,
    action: str,
    resource_type: str,
    actor_id: str | None = None,
    session_id: str | None = None,
    resource_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if os.getenv("ENVIRONMENT", "").lower() == "test":
        return
    await get_database()["auditlogs"].insert_one(
        {
            "actorType": actor_type,
            "actorId": _to_object_id(actor_id),
            "sessionId": _to_object_id(session_id),
            "action": action,
            "resourceType": resource_type,
            "resourceId": _to_object_id(resource_id),
            "ipHash": _hash_optional(ip),
            "userAgentHash": _hash_optional(user_agent),
            "metadata": metadata or {},
            "createdAt": datetime.now(UTC),
        }
    )


def _serialize_log(document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    if payload.get("_id") is not None:
        payload["id"] = str(payload["_id"])
        payload["_id"] = str(payload["_id"])
    for key in ("actorId", "sessionId", "resourceId"):
        if payload.get(key) is not None:
            payload[key] = str(payload[key])
    payload["ipHashPresent"] = bool(payload.get("ipHash"))
    payload["userAgentHashPresent"] = bool(payload.get("userAgentHash"))
    payload.pop("ipHash", None)
    payload.pop("userAgentHash", None)
    return payload


async def list_audit_logs(
    query: AuditLogsQueryInput,
    *,
    repository: AuditRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_audit_repository()
    filters = {
        key: value
        for key, value in query.model_dump(exclude_none=True).items()
        if key not in {"limit", "actorId", "resourceId"}
    }
    if query.actorId:
        filters["actorId"] = _to_object_id(query.actorId) or query.actorId
    if query.resourceId:
        filters["resourceId"] = _to_object_id(query.resourceId) or query.resourceId
    records = await repository.list_audit_logs(filters, query.limit)
    return [_serialize_log(record) for record in records]
