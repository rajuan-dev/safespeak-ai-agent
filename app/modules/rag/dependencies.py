from typing import Annotated

from fastapi import Depends

from app.core.security import Principal, require_ai_consent, require_internal_service
from app.modules.auth.dependencies import require_admin_role

AdminRagRoleDependency = require_admin_role("super_admin", "content_admin")


async def current_rag_admin(
    principal: Annotated[Principal, Depends(AdminRagRoleDependency)],
) -> Principal:
    return principal


async def current_rag_internal(
    _authorized: Annotated[None, Depends(require_internal_service)],
) -> None:
    return None


CurrentRagPrincipal = Annotated[Principal, Depends(require_ai_consent)]
CurrentRagAdminPrincipal = Annotated[Principal, Depends(current_rag_admin)]
CurrentRagInternal = Annotated[None, Depends(current_rag_internal)]
