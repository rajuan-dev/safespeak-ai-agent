from typing import Annotated

from fastapi import Depends

from app.modules.auth.dependencies import Principal, require_admin_role

AdminResourcePrincipal = Annotated[
    Principal, Depends(require_admin_role("super_admin", "content_admin"))
]
