from typing import Any

from fastapi import HTTPException, status

from app.modules.audit.service import create_audit_log

from .repository import TaxonomyRepository, get_taxonomy_repository
from .schema import TaxonomyInput, TaxonomyQueryInput, UpdateTaxonomyInput


def _serialize(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    payload = dict(document)
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
    return payload


async def _audit(actor_id: str, action: str, resource_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action=action,
        resource_type="taxonomy",
        resource_id=resource_id,
        metadata=metadata or {},
    )


async def list_taxonomies(
    actor_id: str,
    query: TaxonomyQueryInput,
    *,
    repository: TaxonomyRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_taxonomy_repository()
    filters = {"deletedAt": {"$exists": False}}
    if query.type:
        filters["type"] = query.type
    if query.isActive is not None:
        filters["isActive"] = query.isActive
    rows = await repository.list_taxonomies(filters)
    await _audit(actor_id, "admin.taxonomies.list", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def get_taxonomy(actor_id: str, taxonomy_id: str, *, repository: TaxonomyRepository | None = None) -> dict[str, Any]:
    repository = repository or get_taxonomy_repository()
    record = await repository.get_taxonomy(taxonomy_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Taxonomy not found")
    await _audit(actor_id, "admin.taxonomies.get", taxonomy_id)
    return _serialize(record)


async def create_taxonomy(actor_id: str, input_data: TaxonomyInput, *, repository: TaxonomyRepository | None = None) -> dict[str, Any]:
    repository = repository or get_taxonomy_repository()
    record = await repository.create_taxonomy(input_data.model_dump(exclude_none=True))
    await _audit(actor_id, "admin.taxonomies.create", str(record["_id"]), {"type": record.get("type")})
    return _serialize(record)


async def update_taxonomy(actor_id: str, taxonomy_id: str, input_data: UpdateTaxonomyInput, *, repository: TaxonomyRepository | None = None) -> dict[str, Any]:
    repository = repository or get_taxonomy_repository()
    record = await repository.update_taxonomy(taxonomy_id, input_data.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Taxonomy not found")
    await _audit(actor_id, "admin.taxonomies.update", taxonomy_id, {"changedFields": list(input_data.model_dump(exclude_none=True).keys())})
    return _serialize(record)


async def delete_taxonomy(actor_id: str, taxonomy_id: str, *, repository: TaxonomyRepository | None = None) -> dict[str, Any]:
    repository = repository or get_taxonomy_repository()
    record = await repository.delete_taxonomy(taxonomy_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Taxonomy not found")
    await _audit(actor_id, "admin.taxonomies.delete", taxonomy_id)
    return _serialize(record)


async def get_taxonomy_dependencies(actor_id: str, taxonomy_id: str, *, repository: TaxonomyRepository | None = None) -> dict[str, Any]:
    repository = repository or get_taxonomy_repository()
    taxonomy = await repository.get_taxonomy(taxonomy_id)
    if not taxonomy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Taxonomy not found")
    historical_reports = await repository.count_reports_using_taxonomy(taxonomy)
    response = {
        "taxonomyId": taxonomy_id,
        "historicalReferences": {
            "reports": historical_reports,
        },
        "canDelete": historical_reports == 0,
    }
    await _audit(actor_id, "admin.taxonomies.dependencies", taxonomy_id, response["historicalReferences"])
    return response
