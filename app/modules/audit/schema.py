from pydantic import BaseModel


class AuditLogsQueryInput(BaseModel):
    actorType: str | None = None
    resourceType: str | None = None
    action: str | None = None
    actorId: str | None = None
    resourceId: str | None = None
    limit: int = 50

