from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.security import Principal, require_user_or_session

SessionPrincipal = Annotated[Principal, Depends(require_user_or_session)]


async def require_anonymous_session(
    principal: SessionPrincipal,
    x_safespeak_session: Annotated[str | None, Header(alias="X-SafeSpeak-Session")] = None,
) -> Principal:
    if not x_safespeak_session or principal.actor_type != "anonymous_session":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Anonymous session is required")
    return principal
