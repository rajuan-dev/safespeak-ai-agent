from typing import Annotated

from fastapi import Depends

from app.modules.auth.dependencies import Principal, require_admin_role

CurrentAdminPrincipal = Annotated[Principal, Depends(require_admin_role())]
SuperAdminPrincipal = Annotated[Principal, Depends(require_admin_role("super_admin"))]
IntegrationAdminPrincipal = Annotated[
    Principal, Depends(require_admin_role("super_admin", "integration_admin"))
]
ContentAdminPrincipal = Annotated[
    Principal, Depends(require_admin_role("super_admin", "content_admin"))
]
AnalyticsPrincipal = Annotated[
    Principal, Depends(require_admin_role("super_admin", "analytics_viewer"))
]
SupportServiceAdminPrincipal = Annotated[
    Principal,
    Depends(require_admin_role("super_admin", "integration_admin", "content_admin")),
]
