import secrets
from typing import Annotated

from bson import ObjectId
from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.core.database import get_database
from app.core.permissions import CONTENT_ADMIN_ROLES
from app.modules.auth.dependencies import (
    Principal,
    authenticate_user,
)
from app.modules.auth.dependencies import (
    authenticate_session_or_user as require_user_or_session,
)


async def require_content_admin(
    principal: Annotated[Principal, Depends(authenticate_user)],
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


async def require_internal_service(
    x_ai_agent_token: Annotated[str | None, Header(alias="X-AI-Agent-Token")] = None,
) -> None:
    expected = get_settings().AI_AGENT_INTERNAL_TOKEN
    if (
        not expected
        or not x_ai_agent_token
        or not secrets.compare_digest(x_ai_agent_token, expected)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal service token")


async def require_ai_or_transcription_consent(
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
    flags = (record or {}).get("flags") or {}
    if not flags.get("process_with_ai") and not flags.get("transcribe_audio"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "process_with_ai or transcribe_audio consent is required for transcription",
        )
    return principal
