from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jwt import InvalidTokenError

from app.core.permissions import ADMIN_ROLES, can_access_admin
from app.modules.sessions.service import get_session_by_token

from .repository import AuthRepository, get_auth_repository
from .security import invalid_token_to_auth_error, verify_access_token

AuthRepositoryDependency = Annotated[AuthRepository, Depends(get_auth_repository)]


@dataclass(frozen=True)
class Principal:
    actor_type: str
    user_id: str | None = None
    session_id: str | None = None
    role: str | None = None
    email: str | None = None
    full_name: str | None = None
    status: str | None = None


def get_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip()


async def optional_authenticate_user(
    authorization: Annotated[str | None, Header()] = None,
    repository: AuthRepositoryDependency = None,
) -> Principal | None:
    token = get_bearer_token(authorization)
    if not token:
        return None
    try:
        payload = verify_access_token(token)
    except InvalidTokenError:
        return None
    except Exception:
        return None
    user = await repository.find_user_by_id(payload.user_id)
    if not user or user["status"] != "active":
        return None
    return Principal(
        actor_type="user",
        user_id=str(user["_id"]),
        role=user["role"],
        email=user["email"],
        full_name=user["fullName"],
        status=user["status"],
    )


async def authenticate_user(
    authorization: Annotated[str | None, Header()] = None,
    repository: AuthRepositoryDependency = None,
) -> Principal:
    token = get_bearer_token(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication token is required")
    try:
        payload = verify_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, invalid_token_to_auth_error(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token") from exc

    user = await repository.find_user_by_id(payload.user_id)
    if not user or user["status"] != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token")
    return Principal(
        actor_type="user",
        user_id=str(user["_id"]),
        role=user["role"],
        email=user["email"],
        full_name=user["fullName"],
        status=user["status"],
    )


async def authenticate_session_or_user(
    authorization: Annotated[str | None, Header()] = None,
    x_safespeak_session: Annotated[str | None, Header(alias="X-SafeSpeak-Session")] = None,
    repository: AuthRepositoryDependency = None,
) -> Principal:
    token = get_bearer_token(authorization)
    if token:
        return await authenticate_user(authorization=authorization, repository=repository)
    if not x_safespeak_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")
    session = await get_session_by_token(x_safespeak_session)
    return Principal(
        actor_type="anonymous_session",
        session_id=session.id,
        user_id=session.user_id,
        role="public_user",
    )


def require_roles(*roles: str) -> Callable[[Principal], Principal]:
    async def dependency(principal: Annotated[Principal, Depends(authenticate_user)]) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return principal

    return dependency


def require_admin_role(*roles: str) -> Callable[[Principal], Principal]:
    async def dependency(principal: Annotated[Principal, Depends(authenticate_user)]) -> Principal:
        if not principal.role or not can_access_admin(principal.role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin permissions are required")
        if roles and principal.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient admin permissions")
        return principal

    return dependency


AuthenticatedUser = Annotated[Principal, Depends(authenticate_user)]
AuthenticatedSessionOrUser = Annotated[Principal, Depends(authenticate_session_or_user)]

__all__ = [
    "ADMIN_ROLES",
    "AuthenticatedSessionOrUser",
    "AuthenticatedUser",
    "Principal",
    "authenticate_session_or_user",
    "authenticate_user",
    "optional_authenticate_user",
    "require_admin_role",
    "require_roles",
]
