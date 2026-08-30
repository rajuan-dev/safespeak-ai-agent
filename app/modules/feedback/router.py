from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_database
from app.core.responses import success
from app.modules.auth.dependencies import (
    Principal,
    authenticate_session_or_user,
    require_admin_role,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])
admin_router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])


def _collection():
    return get_database()["feedback"]


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
        payload["id"] = payload["_id"]
    for key in ("userId", "sessionId", "reviewedBy"):
        if payload.get(key) is not None:
            payload[key] = str(payload[key])
    return payload


@router.post("")
async def create_feedback_route(
    payload: dict[str, Any],
    principal: Annotated[Principal, Depends(authenticate_session_or_user)],
):
    now = datetime.now(UTC)
    document = {
        "userId": ObjectId(principal.user_id) if principal.user_id and ObjectId.is_valid(principal.user_id) else None,
        "sessionId": ObjectId(principal.session_id) if principal.session_id and ObjectId.is_valid(principal.session_id) else None,
        "name": payload.get("name"),
        "email": payload.get("email"),
        "phone": payload.get("phone"),
        "subject": payload.get("subject"),
        "message": payload.get("message"),
        "rating": payload.get("rating"),
        "source": payload.get("source", "user_feedback"),
        "status": "new",
        "metadata": payload.get("metadata") or {},
        "createdAt": now,
        "updatedAt": now,
    }
    result = await _collection().insert_one(document)
    document["_id"] = result.inserted_id
    return success("Feedback submitted", {"feedback": {"id": str(result.inserted_id), "status": "new", "createdAt": now}})


@admin_router.get("")
async def list_admin_feedback_route(
    principal: Annotated[object, Depends(require_admin_role("super_admin"))],
    status: str | None = None,
    source: str | None = None,
    search: str | None = None,
    limit: int = 50,
):
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source
    if search:
        query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"email": {"$regex": search, "$options": "i"}}, {"message": {"$regex": search, "$options": "i"}}]
    cursor = _collection().find(query).sort("createdAt", -1).limit(limit)
    return success("Admin feedback retrieved", {"feedback": [_serialize(item) for item in await cursor.to_list(length=None)]})


@admin_router.patch("/{id}")
async def update_admin_feedback_route(
    id: str,
    payload: dict[str, Any],
    principal: Annotated[Principal, Depends(require_admin_role("super_admin"))],
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Feedback not found")
    updates = {key: value for key, value in payload.items() if key in {"status", "adminNotes"}}
    updates["reviewedBy"] = ObjectId(principal.user_id) if principal.user_id and ObjectId.is_valid(principal.user_id) else principal.user_id
    updates["reviewedAt"] = datetime.now(UTC)
    updates["updatedAt"] = updates["reviewedAt"]
    document = await _collection().find_one_and_update(
        {"_id": ObjectId(id)},
        {"$set": updates},
        return_document=__import__("pymongo").ReturnDocument.AFTER,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return success("Admin feedback updated", {"feedback": _serialize(document)})
