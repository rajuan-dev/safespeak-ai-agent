from fastapi import APIRouter

from app.core.responses import success

from .dependencies import SuperAdminPrincipal
from .schema import AuditLogsQueryInput
from .service import list_audit_logs

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])


@router.get("")
async def list_audit_logs_route(
    principal: SuperAdminPrincipal,
    query: AuditLogsQueryInput = None,
):
    audit_logs = await list_audit_logs(query or AuditLogsQueryInput())
    return success("Audit logs retrieved", {"auditLogs": audit_logs})
