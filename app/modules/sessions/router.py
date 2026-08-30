from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.responses import success
from app.modules.sessions.dependencies import SessionPrincipal, require_anonymous_session
from app.modules.sessions.schema import ConvertToUserInput, CreateAnonymousSessionInput
from app.modules.sessions.service import (
    convert_session_to_user,
    create_anonymous_session,
    get_session_by_token,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/anonymous", status_code=201)
async def create_anonymous_session_route(
    request: Request,
    input_data: CreateAnonymousSessionInput,
):
    result = await create_anonymous_session(
        input_data,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Anonymous session created", result)


@router.get("/current")
async def get_current_session_route(
    request: Request,
    principal: SessionPrincipal,
):
    session_token = request.headers.get("X-SafeSpeak-Session")
    session = await get_session_by_token(session_token) if session_token else principal
    session_data = (
        session.model_dump(by_alias=True)
        if hasattr(session, "model_dump")
        else {
            "id": principal.session_id or principal.user_id or "",
            "userId": principal.user_id,
            "isAnonymous": principal.actor_type == "anonymous_session",
            "language": None,
            "jurisdiction": None,
            "lga": None,
        }
    )
    return success("Current session retrieved", {"session": session_data})


@router.post("/convert-to-user")
async def convert_to_user_route(
    request: Request,
    input_data: ConvertToUserInput,
    principal: Annotated[SessionPrincipal, Depends(require_anonymous_session)],
):
    session = await convert_session_to_user(
        principal.session_id,
        input_data.user_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Session converted to user", {"session": session.model_dump(by_alias=True)})
