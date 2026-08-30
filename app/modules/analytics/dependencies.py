from typing import Annotated

from fastapi import Depends

from app.modules.auth.dependencies import Principal, require_admin_role

CurrentAnalyticsAdmin = Annotated[
    Principal, Depends(require_admin_role("super_admin", "analytics_viewer"))
]

__all__ = ["CurrentAnalyticsAdmin"]
