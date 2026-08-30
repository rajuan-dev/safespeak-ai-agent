from fastapi import APIRouter

from app.core.responses import success

from .dependencies import ContentAdminPrincipal
from .schema import TaxonomyInput, TaxonomyQueryInput, UpdateTaxonomyInput
from .service import (
    create_taxonomy,
    delete_taxonomy,
    get_taxonomy,
    get_taxonomy_dependencies,
    list_taxonomies,
    update_taxonomy,
)

router = APIRouter(prefix="/admin/taxonomies", tags=["admin-taxonomies"])


@router.get("")
async def list_taxonomies_route(principal: ContentAdminPrincipal, query: TaxonomyQueryInput = None):
    taxonomies = await list_taxonomies(principal.user_id or "", query or TaxonomyQueryInput())
    return success("Taxonomies retrieved", {"taxonomies": taxonomies})


@router.get("/{id}")
async def get_taxonomy_route(id: str, principal: ContentAdminPrincipal):
    taxonomy = await get_taxonomy(principal.user_id or "", id)
    return success("Taxonomy retrieved", {"taxonomy": taxonomy})


@router.get("/{id}/dependencies")
async def get_taxonomy_dependencies_route(id: str, principal: ContentAdminPrincipal):
    dependencies = await get_taxonomy_dependencies(principal.user_id or "", id)
    return success("Taxonomy dependencies retrieved", {"dependencies": dependencies})


@router.post("")
async def create_taxonomy_route(input_data: TaxonomyInput, principal: ContentAdminPrincipal):
    taxonomy = await create_taxonomy(principal.user_id or "", input_data)
    return success("Taxonomy created", {"taxonomy": taxonomy})


@router.patch("/{id}")
async def update_taxonomy_route(id: str, input_data: UpdateTaxonomyInput, principal: ContentAdminPrincipal):
    taxonomy = await update_taxonomy(principal.user_id or "", id, input_data)
    return success("Taxonomy updated", {"taxonomy": taxonomy})


@router.delete("/{id}")
async def delete_taxonomy_route(id: str, principal: ContentAdminPrincipal):
    taxonomy = await delete_taxonomy(principal.user_id or "", id)
    return success("Taxonomy deleted", {"taxonomy": taxonomy})
