from typing import Annotated

from fastapi import Depends

from app.modules.auth.dependencies import (
    AuthenticatedSessionOrUser,
    Principal,
    authenticate_session_or_user,
)

CurrentScamShieldPrincipal = Annotated[Principal, Depends(authenticate_session_or_user)]

__all__ = ["AuthenticatedSessionOrUser", "CurrentScamShieldPrincipal"]
