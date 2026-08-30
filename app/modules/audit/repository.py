from typing import Any

from app.config.database import get_database


class AuditRepository:
    def __init__(self) -> None:
        self.audit_logs = get_database()["auditlogs"]

    async def list_audit_logs(self, query: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        cursor = self.audit_logs.find(query).sort("createdAt", -1).limit(limit)
        return await cursor.to_list(length=None)


def get_audit_repository() -> AuditRepository:
    return AuditRepository()
