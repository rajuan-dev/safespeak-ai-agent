from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.config.settings import get_settings
from app.core.responses import success

from .dependencies import ContentAdminPrincipal
from .repository import get_content_repository
from .schema import (
    ContentResourceInput,
    ContentResourceUpdateInput,
    GenerateMicroEducationInput,
    MicroEducationCategoryInput,
    MicroEducationCategoryUpdateInput,
    MicroEducationInput,
    MicroEducationUpdateInput,
)
from .service import (
    create_content_resource,
    create_microeducation_category,
    create_microeducation_item,
    delete_content_resource,
    delete_microeducation_category,
    delete_microeducation_item,
    generate_microeducation_card,
    get_admin_content_resource,
    list_admin_content_resources,
    list_admin_microeducation,
    list_admin_microeducation_categories,
    list_microeducation_cards,
    list_microeducation_categories,
    list_published_content_resources,
    list_published_microeducation,
    parse_json_list,
    update_content_resource,
    update_microeducation_category,
    update_microeducation_item,
)


def _resolve_storage_path(root: Path, storage_key: str) -> Path:
    path = (root / storage_key).resolve()
    if not str(path).startswith(str(root.resolve())):
        raise HTTPException(status_code=400, detail="Invalid storage key")
    return path

content_resources_router = APIRouter(tags=["content"])
admin_content_resources_router = APIRouter(tags=["admin-content"])
admin_microeducation_router = APIRouter(tags=["admin-microeducation"])
OPTIONAL_UPLOAD_FILE = File(default=None)


async def _content_resource_input_from_request(request: Request, update: bool = False):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        payload = {
            "name": form.get("name"),
            "language": form.get("language"),
            "category": form.get("category"),
            "jurisdiction": form.get("jurisdiction"),
            "reviewDate": form.get("reviewDate"),
            "status": form.get("status"),
        }
        model = ContentResourceUpdateInput if update else ContentResourceInput
        return model(**{key: value for key, value in payload.items() if value is not None})
    data = await request.json()
    return (ContentResourceUpdateInput if update else ContentResourceInput)(**data)


async def _microeducation_input_from_request(request: Request, update: bool = False):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        payload = {
            "title": form.get("title"),
            "summary": form.get("summary"),
            "readTimeLabel": form.get("readTimeLabel"),
            "tag": form.get("tag"),
            "cta": form.get("cta"),
            "detailHeading": form.get("detailHeading"),
            "detailSummary": form.get("detailSummary"),
            "detailBody": form.get("detailBody"),
            "detailTakeaway": form.get("detailTakeaway"),
            "imageAlt": form.get("imageAlt"),
            "categoryId": form.get("categoryId"),
            "tone": form.get("tone"),
            "chips": parse_json_list(form.get("chips")),
            "incidentCategories": parse_json_list(form.get("incidentCategories")),
            "matchKeywords": parse_json_list(form.get("matchKeywords")),
            "duration": form.get("duration"),
            "format": form.get("format"),
            "status": form.get("status"),
            "sortOrder": int(form["sortOrder"]) if form.get("sortOrder") is not None else None,
            "views": int(form["views"]) if form.get("views") is not None else None,
        }
        model = MicroEducationUpdateInput if update else MicroEducationInput
        return model(**{key: value for key, value in payload.items() if value is not None})
    data = await request.json()
    return (MicroEducationUpdateInput if update else MicroEducationInput)(**data)


@content_resources_router.get("/content-resources")
async def list_content_resources_route():
    resources = await list_published_content_resources()
    return success("Content resources retrieved", {"resources": resources})


@content_resources_router.get("/content-resources/{id}/download")
async def download_content_resource_route(id: str):
    repository = get_content_repository()
    resource = await repository.get_content_resource(id)
    if not resource or not resource.get("storageKey"):
        raise HTTPException(status_code=404, detail="Content resource file not found")
    root = get_settings().CONTENT_RESOURCE_STORAGE_PATH
    path = _resolve_storage_path(root, resource["storageKey"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Content resource file not found")
    return FileResponse(
        path,
        media_type=resource.get("mimeType") or "application/octet-stream",
        filename=resource.get("originalFileName"),
    )


@content_resources_router.get("/content-resources/{id}/image")
async def content_resource_image_route(id: str):
    repository = get_content_repository()
    resource = await repository.get_content_resource(id)
    if not resource or not resource.get("imageStorageKey"):
        raise HTTPException(status_code=404, detail="Content resource image not found")
    root = get_settings().CONTENT_RESOURCE_STORAGE_PATH
    path = _resolve_storage_path(root, resource["imageStorageKey"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Content resource image not found")
    return FileResponse(
        path,
        media_type=resource.get("imageMimeType") or "application/octet-stream",
        filename=resource.get("imageOriginalFileName"),
    )


@content_resources_router.get("/microeducation")
async def list_microeducation_route():
    items = await list_published_microeducation()
    return success("Micro-education items retrieved", {"items": items})


@content_resources_router.get("/microeducation/categories")
async def list_microeducation_categories_route():
    categories = await list_microeducation_categories()
    return success("Micro-education categories retrieved", {"categories": categories})


@content_resources_router.get("/microeducation/categories/{id}/cards")
async def list_microeducation_cards_route(id: str):
    items = await list_microeducation_cards(id)
    return success("Micro-education category items retrieved", {"items": items})


@content_resources_router.get("/microeducation/{id}/image")
async def microeducation_image_route(id: str):
    repository = get_content_repository()
    item = await repository.get_microeducation(id)
    if not item or not item.get("imageStorageKey"):
        raise HTTPException(status_code=404, detail="Micro-education image not found")
    root = get_settings().MICRO_EDUCATION_IMAGE_STORAGE_PATH
    path = _resolve_storage_path(root, item["imageStorageKey"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Micro-education image not found")
    return FileResponse(
        path,
        media_type=item.get("imageMimeType") or "application/octet-stream",
        filename=item.get("imageOriginalFileName"),
    )


@admin_content_resources_router.get("/admin/content-resources")
async def list_admin_content_resources_route(principal: ContentAdminPrincipal):
    resources = await list_admin_content_resources(principal.user_id or "")
    return success("Admin content resources retrieved", {"resources": resources})


@admin_content_resources_router.get("/admin/content-resources/{id}")
async def get_admin_content_resource_route(id: str, principal: ContentAdminPrincipal):
    resource = await get_admin_content_resource(principal.user_id or "", id)
    return success("Admin content resource retrieved", {"resource": resource})


@admin_content_resources_router.post("/admin/content-resources")
async def create_content_resource_route(
    request: Request,
    principal: ContentAdminPrincipal,
    file: UploadFile | None = OPTIONAL_UPLOAD_FILE,
    image: UploadFile | None = OPTIONAL_UPLOAD_FILE,
):
    resource = await create_content_resource(
        principal.user_id or "",
        await _content_resource_input_from_request(request),
        file,
        image,
    )
    return success("Content resource created", {"resource": resource})


@admin_content_resources_router.patch("/admin/content-resources/{id}")
async def update_content_resource_route(
    id: str,
    request: Request,
    principal: ContentAdminPrincipal,
    file: UploadFile | None = OPTIONAL_UPLOAD_FILE,
    image: UploadFile | None = OPTIONAL_UPLOAD_FILE,
):
    resource = await update_content_resource(
        principal.user_id or "",
        id,
        await _content_resource_input_from_request(request, update=True),
        file,
        image,
    )
    return success("Content resource updated", {"resource": resource})


@admin_content_resources_router.delete("/admin/content-resources/{id}")
async def delete_content_resource_route(id: str, principal: ContentAdminPrincipal):
    resource = await delete_content_resource(principal.user_id or "", id)
    return success("Content resource deleted", {"resource": resource})


@admin_microeducation_router.get("/admin/microeducation")
async def list_admin_microeducation_route(principal: ContentAdminPrincipal):
    items = await list_admin_microeducation(principal.user_id or "")
    return success("Admin micro-education items retrieved", {"items": items})


@admin_microeducation_router.post("/admin/microeducation/generate")
async def generate_microeducation_route(input_data: GenerateMicroEducationInput, principal: ContentAdminPrincipal):
    card = await generate_microeducation_card(input_data)
    return success("Micro-education card generated", {"card": card})


@admin_microeducation_router.get("/admin/microeducation/categories")
async def list_admin_microeducation_categories_route(principal: ContentAdminPrincipal):
    categories = await list_admin_microeducation_categories(principal.user_id or "")
    return success("Micro-education categories retrieved", {"categories": categories})


@admin_microeducation_router.post("/admin/microeducation/categories")
async def create_microeducation_category_route(input_data: MicroEducationCategoryInput, principal: ContentAdminPrincipal):
    category = await create_microeducation_category(principal.user_id or "", input_data)
    return success("Micro-education category created", {"category": category})


@admin_microeducation_router.patch("/admin/microeducation/categories/{id}")
async def update_microeducation_category_route(id: str, input_data: MicroEducationCategoryUpdateInput, principal: ContentAdminPrincipal):
    category = await update_microeducation_category(principal.user_id or "", id, input_data)
    return success("Micro-education category updated", {"category": category})


@admin_microeducation_router.delete("/admin/microeducation/categories/{id}")
async def delete_microeducation_category_route(id: str, principal: ContentAdminPrincipal):
    category = await delete_microeducation_category(principal.user_id or "", id)
    return success("Micro-education category deleted", {"category": category})


@admin_microeducation_router.post("/admin/microeducation")
async def create_microeducation_item_route(
    request: Request,
    principal: ContentAdminPrincipal,
    image: UploadFile | None = OPTIONAL_UPLOAD_FILE,
):
    item = await create_microeducation_item(
        principal.user_id or "",
        await _microeducation_input_from_request(request),
        image,
    )
    return success("Micro-education item created", {"item": item})


@admin_microeducation_router.patch("/admin/microeducation/{id}")
async def update_microeducation_item_route(
    id: str,
    request: Request,
    principal: ContentAdminPrincipal,
    image: UploadFile | None = OPTIONAL_UPLOAD_FILE,
):
    item = await update_microeducation_item(
        principal.user_id or "",
        id,
        await _microeducation_input_from_request(request, update=True),
        image,
    )
    return success("Micro-education item updated", {"item": item})


@admin_microeducation_router.delete("/admin/microeducation/{id}")
async def delete_microeducation_item_route(id: str, principal: ContentAdminPrincipal):
    item = await delete_microeducation_item(principal.user_id or "", id)
    return success("Micro-education item deleted", {"item": item})
