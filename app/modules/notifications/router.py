from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_database
from app.core.responses import success
from app.modules.auth.dependencies import Principal, authenticate_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _db():
    return get_database()


def _user_id(principal) -> ObjectId:
    if not principal.user_id or not ObjectId.is_valid(principal.user_id):
        raise HTTPException(status_code=401, detail="Authentication token is required")
    return ObjectId(principal.user_id)


async def _read_map(user_id: ObjectId, notification_ids: list[str]) -> dict[str, datetime]:
    cursor = _db()["usernotificationreads"].find(
        {"userId": user_id, "notificationId": {"$in": notification_ids}}
    )
    return {
        item["notificationId"]: item.get("readAt")
        for item in await cursor.to_list(length=None)
    }


def _format(notification_id: str, title: str, body: str, created_at: datetime, source_type: str, source_id: str | None = None) -> dict[str, Any]:
    return {
        "id": notification_id,
        "title": title,
        "body": body,
        "timestamp": created_at.isoformat(),
        "dateLabel": created_at.date().isoformat(),
        "type": source_type,
        "severity": "info",
        "createdAt": created_at,
        "sourceType": source_type,
        "sourceId": source_id,
    }


async def _build_notifications(user_id: ObjectId) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []
    reports = await _db()["reports"].find({"userId": user_id, "deletedAt": {"$exists": False}}).sort("updatedAt", -1).limit(50).to_list(length=None)
    for report in reports:
        status = report.get("status", "draft")
        created_at = report.get("updatedAt") or report.get("createdAt") or datetime.now(UTC)
        notifications.append(
            _format(
                f"report:{report['_id']}:status:{status}",
                "Report updated",
                f"Your report is currently {status}.",
                created_at,
                "report_status",
                str(report["_id"]),
            )
        )
    privacy_requests = await _db()["privacyrequests"].find({"userId": user_id}).sort("updatedAt", -1).limit(50).to_list(length=None)
    for request in privacy_requests:
        status = request.get("status", "pending")
        created_at = request.get("updatedAt") or request.get("createdAt") or datetime.now(UTC)
        notifications.append(
            _format(
                f"privacy:{request['_id']}:status:{status}",
                "Privacy request updated",
                f"Your privacy request is currently {status}.",
                created_at,
                "privacy_request",
                str(request["_id"]),
            )
        )
    notifications.sort(key=lambda item: item["createdAt"], reverse=True)
    return notifications


@router.get("")
async def list_notifications_route(
    principal: Annotated[Principal, Depends(authenticate_user)],
    view: str = "all",
    unreadOnly: bool = False,
    limit: int = 50,
):
    user_id = _user_id(principal)
    notifications = await _build_notifications(user_id)
    read_by_id = await _read_map(user_id, [item["id"] for item in notifications])
    today = datetime.now(UTC).date()
    payload = []
    for item in notifications:
        created_date = item["createdAt"].date()
        read_at = read_by_id.get(item["id"])
        item["unread"] = read_at is None
        item["readAt"] = read_at
        if unreadOnly and not item["unread"]:
            continue
        if view == "today" and created_date != today:
            continue
        if view == "past" and created_date == today:
            continue
        payload.append(item)
    return success(
        "Notifications retrieved",
        {
            "notifications": payload[:limit],
            "unreadCount": sum(1 for item in notifications if read_by_id.get(item["id"]) is None),
            "totalCount": len(notifications),
        },
    )


@router.post("/read")
async def mark_notification_read_route(
    payload: dict[str, Any],
    principal: Annotated[Principal, Depends(authenticate_user)],
):
    user_id = _user_id(principal)
    notification_id = payload.get("notificationId")
    if not isinstance(notification_id, str) or not notification_id:
        raise HTTPException(status_code=422, detail="notificationId is required")
    read_at = datetime.now(UTC)
    await _db()["usernotificationreads"].update_one(
        {"userId": user_id, "notificationId": notification_id},
        {"$set": {"userId": user_id, "notificationId": notification_id, "readAt": read_at}},
        upsert=True,
    )
    return success("Notification marked read", {"readReceipt": {"notificationId": notification_id, "readAt": read_at}})


@router.post("/read-all")
async def mark_notifications_read_route(
    payload: dict[str, Any],
    principal: Annotated[Principal, Depends(authenticate_user)],
):
    user_id = _user_id(principal)
    notification_ids = payload.get("notificationIds") or []
    if not isinstance(notification_ids, list) or not notification_ids:
        raise HTTPException(status_code=422, detail="notificationIds is required")
    read_at = datetime.now(UTC)
    for notification_id in notification_ids:
        await _db()["usernotificationreads"].update_one(
            {"userId": user_id, "notificationId": notification_id},
            {"$set": {"userId": user_id, "notificationId": notification_id, "readAt": read_at}},
            upsert=True,
        )
    return success("Notifications marked read", {"readReceipt": {"notificationIds": notification_ids, "readAt": read_at}})
