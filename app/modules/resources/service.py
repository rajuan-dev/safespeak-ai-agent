from typing import Any

from fastapi import HTTPException, status

from app.modules.audit.service import create_audit_log

from .repository import ResourcesRepository, get_resources_repository
from .schema import ResourceInput, ResourceQueryInput, UpdateResourceInput


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
        payload["id"] = payload["_id"]
    return payload


async def list_public_resources(
    query: ResourceQueryInput,
    *,
    repository: ResourcesRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_resources_repository()
    filters = {"deletedAt": {"$exists": False}, "status": "published"}
    rows = await repository.list_resources(filters)
    return [_serialize(row) for row in rows]


async def list_admin_resources(
    actor_id: str,
    query: ResourceQueryInput,
    *,
    repository: ResourcesRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_resources_repository()
    filters = {"deletedAt": {"$exists": False}}
    if query.status:
        filters["status"] = query.status
    rows = await repository.list_resources(filters)
    if query.search:
        token = query.search.lower()
        rows = [row for row in rows if token in (row.get("name") or "").lower()]
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action="admin.resources.list",
        resource_type="resource",
        metadata={"count": len(rows)},
    )
    return [_serialize(row) for row in rows]


async def create_resource(actor_id: str, input_data: ResourceInput, *, repository: ResourcesRepository | None = None) -> dict[str, Any]:
    repository = repository or get_resources_repository()
    resource = await repository.create_resource({**input_data.model_dump(exclude_none=True), "createdBy": actor_id, "updatedBy": actor_id})
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.resources.create", resource_type="resource", resource_id=str(resource["_id"]))
    return _serialize(resource)


async def update_resource(actor_id: str, resource_id: str, input_data: UpdateResourceInput, *, repository: ResourcesRepository | None = None) -> dict[str, Any]:
    repository = repository or get_resources_repository()
    resource = await repository.update_resource(resource_id, {**input_data.model_dump(exclude_none=True), "updatedBy": actor_id})
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.resources.update", resource_type="resource", resource_id=resource_id)
    return _serialize(resource)


async def delete_resource(actor_id: str, resource_id: str, *, repository: ResourcesRepository | None = None) -> dict[str, Any]:
    repository = repository or get_resources_repository()
    resource = await repository.delete_resource(resource_id)
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.resources.delete", resource_type="resource", resource_id=resource_id)
    return _serialize(resource)
