ADMIN_ROLES = {
    "admin",
    "super_admin",
    "content_admin",
    "integration_admin",
    "analytics_viewer",
}

CONTENT_ADMIN_ROLES = {"super_admin", "content_admin"}

PUBLIC_ROLES = {"public_user", "advocate_user", "partner_user"}

USER_ROLES = PUBLIC_ROLES | ADMIN_ROLES

USER_STATUSES = {"active", "inactive", "suspended", "deleted"}


def is_admin_role(role: str) -> bool:
    return role in ADMIN_ROLES


def is_public_role(role: str) -> bool:
    return role in PUBLIC_ROLES


def can_access_admin(role: str) -> bool:
    return is_admin_role(role)
