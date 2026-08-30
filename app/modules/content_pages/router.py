from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_database
from app.core.responses import success
from app.modules.auth.dependencies import require_admin_role

router = APIRouter(prefix="/content-pages", tags=["content-pages"])
admin_router = APIRouter(prefix="/admin/content-pages", tags=["admin-content-pages"])

DEFAULT_CONTENT_PAGES: dict[str, dict[str, Any]] = {
    "landing-page": {
        "heroHeadline": "SafeSpeak",
        "subheading": "Report safely, store evidence, and find support.",
        "primaryButtonLabel": "Get started",
        "primaryButtonUrl": "/dashboard",
        "backgroundVisualsEnabled": True,
    },
    "privacy-policy": {
        "contentHtml": (
            "<h2>SafeSpeak Privacy Policy</h2><p>SafeSpeak asks for explicit consent before "
            "cloud sync, AI processing, transcription, analytics use, warm referrals, or "
            "external agency sharing.</p>"
        ),
    },
    "terms-conditions": {
        "contentHtml": "<h2>SafeSpeak Terms of Use</h2><p>SafeSpeak provides information-only support and does not replace emergency services.</p>",
    },
    "about-us": {
        "eyebrow": "About SafeSpeak",
        "title": "Trauma-informed reporting and support",
        "body": "SafeSpeak helps people document incidents, organise evidence, and find information-only support pathways.",
        "commitments": ["Privacy first", "Trauma-informed language", "Information only"],
    },
}


def _collection():
    return get_database()["contentpages"]


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("_id", None)
    return payload


async def _get_or_create(key: str) -> dict[str, Any]:
    document = await _collection().find_one({"key": key})
    if document:
        return document
    default_content = DEFAULT_CONTENT_PAGES.get(key)
    if default_content is None:
        raise HTTPException(status_code=404, detail="Content page not found")
    now = datetime.now(UTC)
    payload = {
        "key": key,
        "draft": default_content,
        "published": default_content,
        "version": 1,
        "publishedAt": now,
        "createdAt": now,
        "updatedAt": now,
    }
    await _collection().insert_one(payload)
    return payload


@router.get("/{key}")
async def get_public_content_page_route(key: str):
    page = await _get_or_create(key)
    return success(
        "Content page retrieved",
        {
            "contentPage": {
                "key": key,
                "content": page["published"],
                "version": page["version"],
                "publishedAt": page.get("publishedAt"),
                "updatedAt": page.get("updatedAt"),
            }
        },
    )


@admin_router.get("")
async def list_admin_content_pages_route(
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    cursor = _collection().find({}).sort("key", 1)
    pages = [_serialize(item) for item in await cursor.to_list(length=None)]
    return success("Admin content pages retrieved", {"contentPages": pages})


@admin_router.get("/{key}")
async def get_admin_content_page_route(
    key: str,
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    page = await _get_or_create(key)
    return success(
        "Admin content page retrieved",
        {
            "contentPage": {
                "key": key,
                "draft": page["draft"],
                "published": page["published"],
                "version": page["version"],
                "publishedAt": page.get("publishedAt"),
                "createdAt": page.get("createdAt"),
                "updatedAt": page.get("updatedAt"),
                "hasUnpublishedChanges": page["draft"] != page["published"],
            }
        },
    )


@admin_router.post("")
async def create_admin_content_page_route(
    payload: dict[str, Any],
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    key = payload.get("key")
    content = payload.get("content") or payload.get("draft") or {}
    if not isinstance(key, str) or not key:
        raise HTTPException(status_code=422, detail="key is required")
    now = datetime.now(UTC)
    document = {
        "key": key,
        "draft": content,
        "published": content,
        "version": 1,
        "publishedAt": now,
        "createdAt": now,
        "updatedAt": now,
    }
    await _collection().update_one({"key": key}, {"$set": document}, upsert=True)
    return success("Content page created", {"contentPage": document})


@admin_router.patch("/{key}")
async def update_admin_content_page_route(
    key: str,
    payload: dict[str, Any],
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    page = await _get_or_create(key)
    content_patch = payload.get("content", payload)
    if not isinstance(content_patch, dict):
        raise HTTPException(status_code=422, detail="content must be an object")
    draft = {**page["draft"], **content_patch}
    page["draft"] = draft
    page["version"] = int(page.get("version", 0)) + 1
    page["updatedAt"] = datetime.now(UTC)
    await _collection().update_one({"key": key}, {"$set": page})
    return success("Content page saved", {"contentPage": page})


@admin_router.post("/{key}/publish")
async def publish_admin_content_page_route(
    key: str,
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
    payload: dict[str, Any] | None = None,
):
    page = await _get_or_create(key)
    content_patch = (payload or {}).get("content") if isinstance(payload, dict) else None
    if isinstance(content_patch, dict):
        page["draft"] = {**page["draft"], **content_patch}
    page["published"] = page["draft"]
    page["version"] = int(page.get("version", 0)) + 1
    page["publishedAt"] = datetime.now(UTC)
    page["updatedAt"] = page["publishedAt"]
    await _collection().update_one({"key": key}, {"$set": page})
    return success("Content page published", {"contentPage": page})


@admin_router.delete("/{key}")
async def delete_admin_content_page_route(
    key: str,
    principal: Annotated[object, Depends(require_admin_role("super_admin", "content_admin"))],
):
    await _collection().delete_one({"key": key})
    return success("Content page deleted", None)
