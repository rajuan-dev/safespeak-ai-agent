from fastapi import APIRouter

from app.core.responses import success

from .dependencies import AdminResourcePrincipal
from .schema import ResourceInput, ResourceQueryInput, UpdateResourceInput
from .service import (
    create_resource,
    delete_resource,
    list_admin_resources,
    list_public_resources,
    update_resource,
)

router = APIRouter(prefix="/resources", tags=["resources"])
admin_router = APIRouter(prefix="/admin/resources", tags=["admin-resources"])


@router.get("")
async def list_resources_route(query: ResourceQueryInput = None):
    resources = await list_public_resources(query or ResourceQueryInput())
    return success("Resources retrieved", {"resources": resources})


@admin_router.get("")
async def list_admin_resources_route(principal: AdminResourcePrincipal, query: ResourceQueryInput = None):
    resources = await list_admin_resources(principal.user_id or "", query or ResourceQueryInput())
    return success("Admin resources retrieved", {"resources": resources})


@admin_router.post("")
async def create_resource_route(input_data: ResourceInput, principal: AdminResourcePrincipal):
    resource = await create_resource(principal.user_id or "", input_data)
    return success("Resource created", {"resource": resource})


@admin_router.patch("/{id}")
async def update_resource_route(id: str, input_data: UpdateResourceInput, principal: AdminResourcePrincipal):
    resource = await update_resource(principal.user_id or "", id, input_data)
    return success("Resource updated", {"resource": resource})


@admin_router.delete("/{id}")
async def delete_resource_route(id: str, principal: AdminResourcePrincipal):
    resource = await delete_resource(principal.user_id or "", id)
    return success("Resource deleted", {"resource": resource})
