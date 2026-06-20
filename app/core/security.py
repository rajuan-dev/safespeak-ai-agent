import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import jwt
from bson import ObjectId
from fastapi import Depends, Header, HTTPException, status
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.core.database import get_database

ADMIN_ROLES = {"admin", "super_admin", "content_admin", "integration_admin", "analytics_viewer"}
CONTENT_ADMIN_ROLES = {"super_admin", "content_admin"}


@dataclass(frozen=True)
class Principal:
    actor_type: str
    user_id: str | None = None
    session_id: str | None = None
    role: str | None = None


async def _user_from_bearer(authorization: str) -> Principal:
    settings = get_settings()
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.JWT_ACCESS_SECRET, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token") from exc

    user_id = payload.get("userId")
    if not isinstance(user_id, str) or not ObjectId.is_valid(user_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token")

    user = await get_database()["users"].find_one(
        {"_id": ObjectId(user_id), "status": "active"},
        {"role": 1},
    )
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token")
    return Principal(actor_type="user", user_id=user_id, role=str(user.get("role", "")))


async def require_user_or_session(
    authorization: Annotated[str | None, Header()] = None,
    x_safespeak_session: Annotated[str | None, Header(alias="X-SafeSpeak-Session")] = None,
) -> Principal:
    if authorization and authorization.startswith("Bearer "):
        return await _user_from_bearer(authorization)
    if not x_safespeak_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")

    token_hash = hashlib.sha256(x_safespeak_session.encode()).hexdigest()
    session = await get_database()["anonymoussessions"].find_one(
        {"sessionTokenHash": token_hash, "expiresAt": {"$gt": datetime.now(UTC)}},
        {"_id": 1, "userId": 1},
    )
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    return Principal(
        actor_type="anonymous_session",
        session_id=str(session["_id"]),
        user_id=str(session["userId"]) if session.get("userId") else None,
    )


async def require_content_admin(
    principal: Annotated[Principal, Depends(require_user_or_session)],
) -> Principal:
    if principal.role not in CONTENT_ADMIN_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient admin permissions")
    return principal


async def require_ai_consent(
    principal: Annotated[Principal, Depends(require_user_or_session)],
) -> Principal:
    owner_filter: dict[str, ObjectId]
    if principal.user_id and ObjectId.is_valid(principal.user_id):
        owner_filter = {"userId": ObjectId(principal.user_id)}
    elif principal.session_id and ObjectId.is_valid(principal.session_id):
        owner_filter = {"sessionId": ObjectId(principal.session_id)}
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication principal")

    record = await get_database()["consentrecords"].find_one(
        owner_filter,
        sort=[("version", -1)],
        projection={"flags": 1},
    )
    if not record or not (record.get("flags") or {}).get("process_with_ai"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "process_with_ai consent is required for AI processing",
        )
    return principal
