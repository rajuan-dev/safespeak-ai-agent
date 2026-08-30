from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.config.database import get_database
from app.config.settings import get_settings
from app.core.responses import success
from app.modules.auth.dependencies import require_admin_role

router = APIRouter(prefix="/media-assets", tags=["media-assets"])
admin_router = APIRouter(prefix="/admin/media-assets", tags=["admin-media-assets"])
REQUIRED_MEDIA_FILE = File(...)
REQUIRED_TEXT_FORM = Form(...)
OPTIONAL_TEXT_FORM = Form(default=None)
PUBLISHED_STATUS_FORM = Form("published")
OPTIONAL_BOOL_FORM_FALSE = Form(default=False)


def _collection():
    return get_database()["mediaassets"]


def _root() -> Path:
    root = get_settings().MEDIA_ASSET_STORAGE_PATH
    root.mkdir(parents=True, exist_ok=True)
    return root


def _storage_path(storage_key: str) -> Path:
    path = (_root() / storage_key).resolve()
    if not str(path).startswith(str(_root().resolve())):
        raise HTTPException(status_code=400, detail="Invalid media asset storage key")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(document["_id"])
    return {
        "id": asset_id,
        "title": document.get("title"),
        "subtitle": document.get("subtitle"),
        "bodyText": document.get("bodyText"),
        "category": document.get("category"),
        "status": document.get("status"),
        "createdDate": document.get("createdDate"),
        "expirationDate": document.get("expirationDate"),
        "offlineCachingEnabled": bool(document.get("offlineCachingEnabled", False)),
        "primaryCta": document.get("primaryCta"),
        "secondaryButton": document.get("secondaryButton"),
        "originalFileName": document.get("originalFileName"),
        "mimeType": document.get("mimeType"),
        "fileSizeBytes": document.get("fileSizeBytes"),
        "imagePath": f"/api/v1/media-assets/{asset_id}/file",
        "createdAt": document.get("createdAt"),
        "updatedAt": document.get("updatedAt"),
    }


async def _save_upload(file: UploadFile) -> tuple[str, int]:
    payload = await file.read()
    if len(payload) > get_settings().MEDIA_ASSET_MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Media asset exceeds the size limit")
    storage_key = f"{datetime.now(UTC).date().isoformat()}/{uuid4().hex}-{Path(file.filename or 'asset').name}"
    _storage_path(storage_key).write_bytes(payload)
    return storage_key, len(payload)


@router.get("")
async def list_public_media_assets_route(category: str | None = None):
    query: dict[str, Any] = {"deletedAt": {"$exists": False}, "status": "published"}
    if category:
        query["category"] = category
    cursor = _collection().find(query).sort("createdAt", -1)
    return success("Media assets retrieved", {"assets": [_serialize(item) for item in await cursor.to_list(length=None)]})


@router.get("/{id}")
async def get_public_media_asset_route(id: str):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Media asset not found")
    asset = await _collection().find_one({"_id": ObjectId(id), "deletedAt": {"$exists": False}})
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return success("Media asset retrieved", {"asset": _serialize(asset)})


@router.get("/{id}/file")
async def get_public_media_asset_file_route(id: str):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Media asset not found")
    asset = await _collection().find_one({"_id": ObjectId(id), "deletedAt": {"$exists": False}, "status": "published"})
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    path = _storage_path(asset["storageKey"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Media asset file not found")
    return FileResponse(path, media_type=asset.get("mimeType") or "application/octet-stream", filename=asset.get("originalFileName"))


@admin_router.get("")
async def list_admin_media_assets_route(
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))]
):
    cursor = _collection().find({"deletedAt": {"$exists": False}}).sort("createdAt", -1)
    return success("Admin media assets retrieved", {"assets": [_serialize(item) for item in await cursor.to_list(length=None)]})


@admin_router.get("/{id}")
async def get_admin_media_asset_route(
    id: str,
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Media asset not found")
    asset = await _collection().find_one({"_id": ObjectId(id), "deletedAt": {"$exists": False}})
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return success("Admin media asset retrieved", {"asset": _serialize(asset)})


@admin_router.post("")
async def create_media_asset_route(
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
    title: str = REQUIRED_TEXT_FORM,
    subtitle: str = REQUIRED_TEXT_FORM,
    bodyText: str = REQUIRED_TEXT_FORM,
    category: str = REQUIRED_TEXT_FORM,
    status: str = PUBLISHED_STATUS_FORM,
    createdDate: str | None = OPTIONAL_TEXT_FORM,
    expirationDate: str | None = OPTIONAL_TEXT_FORM,
    offlineCachingEnabled: bool = OPTIONAL_BOOL_FORM_FALSE,
    primaryCta: str | None = OPTIONAL_TEXT_FORM,
    secondaryButton: str | None = OPTIONAL_TEXT_FORM,
    file: UploadFile = REQUIRED_MEDIA_FILE,
):
    storage_key, size = await _save_upload(file)
    now = datetime.now(UTC)
    document = {
        "title": title,
        "subtitle": subtitle,
        "bodyText": bodyText,
        "category": category,
        "status": status,
        "createdDate": createdDate,
        "expirationDate": expirationDate,
        "offlineCachingEnabled": offlineCachingEnabled,
        "primaryCta": primaryCta,
        "secondaryButton": secondaryButton,
        "originalFileName": file.filename,
        "mimeType": file.content_type,
        "fileSizeBytes": size,
        "storageKey": storage_key,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await _collection().insert_one(document)
    document["_id"] = result.inserted_id
    return success("Media asset created", {"asset": _serialize(document)})


@admin_router.patch("/{id}")
async def update_media_asset_route(
    id: str,
    request: Request,
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    updates = dict(await request.form()) if "multipart/form-data" in (request.headers.get("content-type") or "") else await request.json()
    file = updates.pop("file", None)
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Media asset not found")
    document = await _collection().find_one({"_id": ObjectId(id), "deletedAt": {"$exists": False}})
    if not document:
        raise HTTPException(status_code=404, detail="Media asset not found")
    if isinstance(file, UploadFile):
        storage_key, size = await _save_upload(file)
        updates["storageKey"] = storage_key
        updates["originalFileName"] = file.filename
        updates["mimeType"] = file.content_type
        updates["fileSizeBytes"] = size
    updates["updatedAt"] = datetime.now(UTC)
    await _collection().update_one({"_id": document["_id"]}, {"$set": updates})
    updated = await _collection().find_one({"_id": document["_id"]})
    return success("Media asset updated", {"asset": _serialize(updated)})


@admin_router.delete("/{id}")
async def delete_media_asset_route(
    id: str,
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Media asset not found")
    document = await _collection().find_one({"_id": ObjectId(id), "deletedAt": {"$exists": False}})
    if not document:
        raise HTTPException(status_code=404, detail="Media asset not found")
    await _collection().update_one({"_id": document["_id"]}, {"$set": {"deletedAt": datetime.now(UTC)}})
    return success("Media asset deleted", None)
