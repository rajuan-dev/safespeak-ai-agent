import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config.settings import get_settings
from app.modules.audit.service import create_audit_log

from .repository import ContentRepository, get_content_repository
from .schema import (
    ContentResourceInput,
    ContentResourceUpdateInput,
    GenerateMicroEducationInput,
    MicroEducationCategoryInput,
    MicroEducationCategoryUpdateInput,
    MicroEducationInput,
    MicroEducationUpdateInput,
)


def _content_storage_root() -> Path:
    root = get_settings().CONTENT_RESOURCE_STORAGE_PATH
    root.mkdir(parents=True, exist_ok=True)
    return root


def _microeducation_storage_root() -> Path:
    root = get_settings().MICRO_EDUCATION_IMAGE_STORAGE_PATH
    root.mkdir(parents=True, exist_ok=True)
    return root


def _storage_path(root: Path, storage_key: str) -> Path:
    path = (root / storage_key).resolve()
    if not str(path).startswith(str(root.resolve())):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid storage key")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def _save_upload(file: UploadFile, *, root: Path, max_size: int, prefix: str) -> tuple[str, int]:
    payload = await file.read()
    if len(payload) > max_size:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Uploaded file exceeds the size limit")
    file_name = Path(file.filename or "upload.bin").name
    storage_key = f"{prefix}/{datetime.now(UTC).date().isoformat()}/{uuid4().hex}-{file_name}"
    _storage_path(root, storage_key).write_bytes(payload)
    return storage_key, len(payload)


def _serialize(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    payload = dict(document)
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
        payload["id"] = payload["_id"]
    return payload


def _resource_paths(resource_id: str) -> dict[str, str]:
    return {
        "downloadPath": f"/api/v1/content-resources/{resource_id}/download",
        "imagePath": f"/api/v1/content-resources/{resource_id}/image",
    }


def _resource_display_status(document: dict[str, Any]) -> str:
    status_value = document.get("status")
    if status_value == "draft":
        return "Draft"
    if status_value == "archived":
        return "Archived"
    return "Active"


def _content_resource_payload(document: dict[str, Any]) -> dict[str, Any]:
    payload = _serialize(document) or {}
    payload.update(_resource_paths(payload.get("id", "")))
    payload["displayStatus"] = _resource_display_status(payload)
    return payload


def _microeducation_payload(document: dict[str, Any], categories_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = _serialize(document) or {}
    if payload.get("categoryId") and categories_by_id:
        payload["category"] = categories_by_id.get(payload["categoryId"])
    payload["imagePath"] = payload.get("imagePath")
    return payload


async def list_published_content_resources(*, repository: ContentRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_content_repository()
    rows = await repository.list_content_resources({"deletedAt": {"$exists": False}, "status": "published"})
    return [_content_resource_payload(row) for row in rows]


async def list_admin_content_resources(actor_id: str, *, repository: ContentRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_content_repository()
    rows = await repository.list_content_resources({"deletedAt": {"$exists": False}})
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.content_resources.list", resource_type="content_resource", metadata={"count": len(rows)})
    return [_content_resource_payload(row) for row in rows]


async def get_admin_content_resource(actor_id: str, resource_id: str, *, repository: ContentRepository | None = None) -> dict[str, Any]:
    repository = repository or get_content_repository()
    resource = await repository.get_content_resource(resource_id)
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content resource not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.content_resources.get", resource_type="content_resource", resource_id=resource_id)
    return _content_resource_payload(resource)


async def create_content_resource(
    actor_id: str,
    input_data: ContentResourceInput,
    file: UploadFile | None = None,
    image: UploadFile | None = None,
    *,
    repository: ContentRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_content_repository()
    payload = input_data.model_dump(exclude_none=True)
    if file:
        storage_key, size = await _save_upload(
            file,
            root=_content_storage_root(),
            max_size=get_settings().CONTENT_RESOURCE_MAX_FILE_SIZE_BYTES,
            prefix="files",
        )
        payload.update(
            {
                "originalFileName": file.filename,
                "mimeType": file.content_type,
                "fileSizeBytes": size,
                "storageKey": storage_key,
            }
        )
    if image:
        image_storage_key, image_size = await _save_upload(
            image,
            root=_content_storage_root(),
            max_size=get_settings().CONTENT_RESOURCE_MAX_FILE_SIZE_BYTES,
            prefix="images",
        )
        payload.update(
            {
                "imageOriginalFileName": image.filename,
                "imageMimeType": image.content_type,
                "imageSizeBytes": image_size,
                "imageStorageKey": image_storage_key,
            }
        )
    payload.update({"createdBy": actor_id, "updatedBy": actor_id})
    record = await repository.create_content_resource(payload)
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action="admin.content_resources.create",
        resource_type="content_resource",
        resource_id=str(record["_id"]),
    )
    return _content_resource_payload(record)


async def update_content_resource(
    actor_id: str,
    resource_id: str,
    input_data: ContentResourceUpdateInput,
    file: UploadFile | None = None,
    image: UploadFile | None = None,
    *,
    repository: ContentRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_content_repository()
    updates = input_data.model_dump(exclude_none=True)
    if file:
        storage_key, size = await _save_upload(
            file,
            root=_content_storage_root(),
            max_size=get_settings().CONTENT_RESOURCE_MAX_FILE_SIZE_BYTES,
            prefix="files",
        )
        updates.update({"originalFileName": file.filename, "mimeType": file.content_type, "fileSizeBytes": size, "storageKey": storage_key})
    if image:
        image_storage_key, image_size = await _save_upload(
            image,
            root=_content_storage_root(),
            max_size=get_settings().CONTENT_RESOURCE_MAX_FILE_SIZE_BYTES,
            prefix="images",
        )
        updates.update(
            {
                "imageOriginalFileName": image.filename,
                "imageMimeType": image.content_type,
                "imageSizeBytes": image_size,
                "imageStorageKey": image_storage_key,
            }
        )
    updates["updatedBy"] = actor_id
    record = await repository.update_content_resource(resource_id, updates)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content resource not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.content_resources.update", resource_type="content_resource", resource_id=resource_id)
    return _content_resource_payload(record)


async def delete_content_resource(actor_id: str, resource_id: str, *, repository: ContentRepository | None = None) -> dict[str, Any]:
    repository = repository or get_content_repository()
    record = await repository.delete_content_resource(resource_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content resource not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.content_resources.delete", resource_type="content_resource", resource_id=resource_id)
    return _content_resource_payload(record)


async def list_published_microeducation(*, repository: ContentRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_content_repository()
    categories = await repository.list_microeducation_categories({"deletedAt": {"$exists": False}, "status": "published"})
    items = await repository.list_microeducation({"deletedAt": {"$exists": False}, "status": "published"})
    categories_by_id = {str(item["_id"]): _serialize(item) for item in categories}
    return [_microeducation_payload(item, categories_by_id) for item in items]


async def list_microeducation_categories(*, repository: ContentRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_content_repository()
    categories = await repository.list_microeducation_categories({"deletedAt": {"$exists": False}, "status": "published"})
    return [_serialize(item) for item in categories]


async def list_microeducation_cards(category_id: str, *, repository: ContentRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_content_repository()
    items = await repository.list_microeducation({"deletedAt": {"$exists": False}, "status": "published", "categoryId": category_id})
    return [_serialize(item) for item in items]


async def list_admin_microeducation(actor_id: str, *, repository: ContentRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_content_repository()
    categories = await repository.list_microeducation_categories({"deletedAt": {"$exists": False}})
    items = await repository.list_microeducation({"deletedAt": {"$exists": False}})
    categories_by_id = {str(item["_id"]): _serialize(item) for item in categories}
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.microeducation.list", resource_type="microeducation", metadata={"count": len(items)})
    return [_microeducation_payload(item, categories_by_id) for item in items]


async def list_admin_microeducation_categories(
    actor_id: str,
    *,
    repository: ContentRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_content_repository()
    categories = await repository.list_microeducation_categories({"deletedAt": {"$exists": False}})
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action="admin.microeducation.categories.list",
        resource_type="microeducation_category",
        metadata={"count": len(categories)},
    )
    return [_serialize(item) for item in categories]


async def create_microeducation_category(
    actor_id: str,
    input_data: MicroEducationCategoryInput,
    *,
    repository: ContentRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_content_repository()
    record = await repository.create_microeducation_category(input_data.model_dump(exclude_none=True))
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action="admin.microeducation.categories.create",
        resource_type="microeducation_category",
        resource_id=str(record["_id"]),
    )
    return _serialize(record)


async def update_microeducation_category(
    actor_id: str,
    category_id: str,
    input_data: MicroEducationCategoryUpdateInput,
    *,
    repository: ContentRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_content_repository()
    record = await repository.update_microeducation_category(category_id, input_data.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Micro-education category not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.microeducation.categories.update", resource_type="microeducation_category", resource_id=category_id)
    return _serialize(record)


async def delete_microeducation_category(actor_id: str, category_id: str, *, repository: ContentRepository | None = None) -> dict[str, Any]:
    repository = repository or get_content_repository()
    record = await repository.delete_microeducation_category(category_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Micro-education category not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.microeducation.categories.delete", resource_type="microeducation_category", resource_id=category_id)
    return _serialize(record)


async def generate_microeducation_card(input_data: GenerateMicroEducationInput) -> dict[str, Any]:
    return {
        "title": input_data.topic,
        "summary": f"Introductory guidance about {input_data.topic}.",
        "readTimeLabel": "3 min",
        "tag": input_data.language or "en",
        "cta": "Learn more",
        "detailHeading": input_data.topic,
        "detailSummary": "Generated draft content for admin review.",
        "detailBody": f"This draft card explains {input_data.topic} in a supportive, information-only way.",
        "detailTakeaway": "Use this card as a reviewed draft before publishing.",
        "tone": input_data.tone or "blue",
        "chips": [],
        "duration": "quick",
        "format": "guide",
        "status": "draft",
        "sortOrder": 0,
        "views": 0,
        "categoryId": input_data.categoryId,
    }


async def create_microeducation_item(
    actor_id: str,
    input_data: MicroEducationInput,
    image: UploadFile | None = None,
    *,
    repository: ContentRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_content_repository()
    payload = input_data.model_dump(exclude_none=True)
    if image:
        image_storage_key, image_size = await _save_upload(
            image,
            root=_microeducation_storage_root(),
            max_size=get_settings().MICRO_EDUCATION_IMAGE_MAX_FILE_SIZE_BYTES,
            prefix="images",
        )
        payload.update(
            {
                "imageOriginalFileName": image.filename,
                "imageMimeType": image.content_type,
                "imageSizeBytes": image_size,
                "imageStorageKey": image_storage_key,
            }
        )
    record = await repository.create_microeducation(payload)
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.microeducation.create", resource_type="microeducation", resource_id=str(record["_id"]))
    payload = _serialize(record)
    payload["imagePath"] = f"/api/v1/microeducation/{payload['id']}/image"
    return payload


async def update_microeducation_item(
    actor_id: str,
    item_id: str,
    input_data: MicroEducationUpdateInput,
    image: UploadFile | None = None,
    *,
    repository: ContentRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_content_repository()
    updates = input_data.model_dump(exclude_none=True)
    if image:
        image_storage_key, image_size = await _save_upload(
            image,
            root=_microeducation_storage_root(),
            max_size=get_settings().MICRO_EDUCATION_IMAGE_MAX_FILE_SIZE_BYTES,
            prefix="images",
        )
        updates.update({"imageOriginalFileName": image.filename, "imageMimeType": image.content_type, "imageSizeBytes": image_size, "imageStorageKey": image_storage_key})
    record = await repository.update_microeducation(item_id, updates)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Micro-education item not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.microeducation.update", resource_type="microeducation", resource_id=item_id)
    payload = _serialize(record)
    payload["imagePath"] = f"/api/v1/microeducation/{payload['id']}/image"
    return payload


async def delete_microeducation_item(actor_id: str, item_id: str, *, repository: ContentRepository | None = None) -> dict[str, Any]:
    repository = repository or get_content_repository()
    record = await repository.delete_microeducation(item_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Micro-education item not found")
    await create_audit_log(actor_type="user", actor_id=actor_id, action="admin.microeducation.delete", resource_type="microeducation", resource_id=item_id)
    return _serialize(record)


def parse_json_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            return [value]
    return None
