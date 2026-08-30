from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.config.settings import get_settings
from app.modules.audit.service import create_audit_log
from app.modules.auth.security import hash_password

from .model import PLATFORM_HEALTH_CHECKS
from .repository import AdminRepository, get_admin_repository
from .schema import (
    CreateAdminUserInput,
    DestinationInput,
    DestinationsQueryInput,
    NotificationReadAllInput,
    NotificationReadInput,
    NotificationsQueryInput,
    PrivacyRequestsQueryInput,
    ReportDeliveriesQueryInput,
    SubmissionTemplateInput,
    SubmissionTemplatesQueryInput,
    SupportServiceInput,
    SupportServicesQueryInput,
    UpdateAdminUserInput,
    UpdateDestinationInput,
    UpdatePrivacyRequestInput,
    UpdateSubmissionTemplateInput,
    UpdateSupportServiceInput,
    UpdateWarmReferralInput,
    UsersQueryInput,
    WarmReferralsQueryInput,
)


def _serialize(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    payload = dict(document)
    payload.pop("passwordHash", None)
    payload.pop("refreshTokenHash", None)
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
    for key in ("userId", "sessionId", "reviewedBy", "destinationId", "reportId", "templateId", "actorId", "resourceId", "serviceId"):
        if payload.get(key) is not None:
            payload[key] = str(payload[key])
    return payload


async def _audit(actor_id: str, action: str, resource_type: str, resource_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata or {},
    )


async def get_admin_dashboard(*, repository: AdminRepository | None = None) -> dict[str, int]:
    repository = repository or get_admin_repository()
    return {
        "users": await repository.count_documents("users", {}),
        "reports": await repository.count_documents("reports", {"deletedAt": {"$exists": False}}),
        "knowledgeSources": await repository.count_documents("rag_sources", {"deletedAt": {"$exists": False}}),
        "openPrivacyRequests": await repository.count_documents("privacy_requests", {"status": {"$in": ["pending", "in_review"]}}),
    }


async def list_admin_users(actor_id: str, query: UsersQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    filters: dict[str, Any] = {}
    if query.role:
        filters["role"] = query.role
    if query.status:
        filters["status"] = query.status
    rows = await repository.list_users(filters, query.limit)
    if query.search:
        token = query.search.lower()
        rows = [row for row in rows if token in (row.get("email") or "").lower() or token in (row.get("fullName") or "").lower()]
    await _audit(actor_id, "admin.users.list", "user", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def create_admin_user(actor_id: str, input_data: CreateAdminUserInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.create_user(
        {
            "email": input_data.email,
            "fullName": input_data.fullName,
            "passwordHash": hash_password(input_data.password),
            "role": input_data.role,
            "status": input_data.status,
            "authProvider": "local",
            "isEmailVerified": True,
        }
    )
    await _audit(actor_id, "admin.users.create", "user", str(record["_id"]), {"role": input_data.role})
    return _serialize(record)


async def update_admin_user(actor_id: str, user_id: str, input_data: UpdateAdminUserInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.update_user(user_id, input_data.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await _audit(actor_id, "admin.users.update", "user", user_id, {"changedFields": list(input_data.model_dump(exclude_none=True).keys())})
    return _serialize(record)


async def list_admin_destinations(actor_id: str, query: DestinationsQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    filters = {"deletedAt": {"$exists": False}}
    for key, value in query.model_dump(exclude_none=True).items():
        filters[key] = value
    rows = await repository.list_destinations(filters)
    await _audit(actor_id, "admin.destinations.list", "destination", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def create_admin_destination(actor_id: str, input_data: DestinationInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.create_destination(input_data.model_dump(exclude_none=True))
    await _audit(actor_id, "admin.destinations.create", "destination", str(record["_id"]))
    return _serialize(record)


async def update_admin_destination(actor_id: str, destination_id: str, input_data: UpdateDestinationInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.update_destination(destination_id, input_data.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Destination not found")
    await _audit(actor_id, "admin.destinations.update", "destination", destination_id)
    return _serialize(record)


async def list_admin_submission_templates(actor_id: str, query: SubmissionTemplatesQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    filters = {"deletedAt": {"$exists": False}}
    for key, value in query.model_dump(exclude_none=True).items():
        filters[key] = value
    rows = await repository.list_templates(filters)
    await _audit(actor_id, "admin.submission_templates.list", "submission_template", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def create_admin_submission_template(
    actor_id: str,
    input_data: SubmissionTemplateInput,
    *,
    repository: AdminRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.create_template(input_data.model_dump(exclude_none=True))
    await _audit(actor_id, "admin.submission_templates.create", "submission_template", str(record["_id"]))
    return _serialize(record)


async def update_admin_submission_template(
    actor_id: str,
    template_id: str,
    input_data: UpdateSubmissionTemplateInput,
    *,
    repository: AdminRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.update_template(template_id, input_data.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission template not found")
    await _audit(actor_id, "admin.submission_templates.update", "submission_template", template_id)
    return _serialize(record)


async def list_admin_report_deliveries(actor_id: str, query: ReportDeliveriesQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    filters = {"deletedAt": {"$exists": False}}
    if query.status:
        filters["status"] = query.status
    if query.destinationType:
        filters["destinationType"] = query.destinationType
    if query.channel:
        filters["channel"] = query.channel
    rows = await repository.list_report_deliveries(filters, query.limit)
    await _audit(actor_id, "admin.report_deliveries.list", "report_submission", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def list_admin_knowledge_sources(actor_id: str, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    rows = await repository.list_knowledge_sources()
    await _audit(actor_id, "admin.knowledge_sources.list", "rag_knowledge_source", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def list_admin_educational_content(actor_id: str, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    bundle = await repository.list_educational_content()
    await _audit(actor_id, "admin.educational_content.list", "content_bundle", metadata={"resources": len(bundle["resources"]), "microeducation": len(bundle["microeducation"])})
    return {
        "resources": [_serialize(item) for item in bundle["resources"]],
        "microeducation": [_serialize(item) for item in bundle["microeducation"]],
    }


async def get_admin_data_protection_overview(actor_id: str, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    pending = await repository.count_documents("privacy_requests", {"status": "pending"})
    in_review = await repository.count_documents("privacy_requests", {"status": "in_review"})
    completed = await repository.count_documents("privacy_requests", {"status": "completed"})
    await _audit(actor_id, "admin.data_protection.overview", "privacy_request")
    return {"pending": pending, "inReview": in_review, "completed": completed}


async def get_admin_ai_engine_overview(actor_id: str, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    interactions = await repository.count_documents("ai_interactions", {})
    await _audit(actor_id, "admin.ai_engine.overview", "ai_interaction")
    return {
        "totalInteractions": interactions,
        "guardrails": {"legalAdvicePrevention": True, "safetyDisclaimers": True},
    }


async def get_admin_language_packs_overview(actor_id: str, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    resources = await repository.count_documents("content_resources", {"deletedAt": {"$exists": False}})
    await _audit(actor_id, "admin.language_packs.overview", "content_resource")
    return {"contentResources": resources, "fallbackLanguage": "en"}


async def get_admin_intelligence_center_overview(actor_id: str, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    dashboard = await get_admin_dashboard(repository=repository)
    await _audit(actor_id, "admin.insights.incident_insights.overview", "report")
    return {
        "summary": dashboard,
        "generatedAt": datetime.now(UTC).isoformat(),
        "anonymisedOnly": True,
    }


async def get_admin_platform_health(actor_id: str) -> dict[str, Any]:
    settings = get_settings()
    checks = PLATFORM_HEALTH_CHECKS
    await _audit(actor_id, "admin.platform_health.overview", "platform")
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "overallStatus": "ready",
        "service": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "apiPrefix": settings.API_PREFIX,
            "uptimeSeconds": 0,
            "uptimeLabel": "Active",
        },
        "stats": [
            {"label": "Admin routes", "value": "online", "helper": "Core enterprise routes are mounted in FastAPI."},
            {"label": "Analytics policy", "value": "anonymised", "helper": "Analytics exports remain privacy-protected."},
        ],
        "checks": checks,
        "blockers": [],
        "warnings": [],
        "counts": {"checks": len(checks), "ready": len(checks), "warnings": 0, "blocked": 0},
        "configuration": {"apiPrefix": settings.API_PREFIX, "environment": settings.ENVIRONMENT},
        "footerNote": "Review live infrastructure and environment secrets during final cutover validation.",
    }


async def list_admin_privacy_requests(actor_id: str, query: PrivacyRequestsQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    filters = {}
    if query.status:
        filters["status"] = query.status
    rows = await repository.list_privacy_requests(filters, query.limit)
    await _audit(actor_id, "admin.privacy_requests.list", "privacy_request", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def update_admin_privacy_request(actor_id: str, request_id: str, input_data: UpdatePrivacyRequestInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    updates = {**input_data.model_dump(exclude_none=True), "reviewedAt": datetime.now(UTC), "reviewedBy": actor_id}
    record = await repository.update_privacy_request(request_id, updates)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Privacy request not found")
    await _audit(actor_id, "admin.privacy_requests.update", "privacy_request", request_id, {"status": input_data.status})
    return _serialize(record)


async def list_admin_notifications(actor_id: str, query: NotificationsQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    audit_logs = await repository.list_recent_audit_logs(query.limit)
    notifications: list[dict[str, Any]] = []
    for log in audit_logs:
        notification_id = str(log.get("_id"))
        read_state = await repository.find_notification_read(actor_id, notification_id)
        notifications.append(
            {
                "id": notification_id,
                "title": log.get("action"),
                "body": f"{log.get('resourceType')} activity recorded",
                "createdAt": log.get("createdAt"),
                "read": bool(read_state),
            }
        )
    await _audit(actor_id, "admin.notifications.list", "notification", metadata={"count": len(notifications)})
    return notifications


async def mark_admin_notification_read(actor_id: str, input_data: NotificationReadInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    receipt = await repository.mark_notification_read(actor_id, input_data.notificationId)
    await _audit(actor_id, "admin.notifications.read", "notification", input_data.notificationId)
    return _serialize(receipt)


async def mark_admin_notifications_read_all(actor_id: str, input_data: NotificationReadAllInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    notifications = await list_admin_notifications(actor_id, NotificationsQueryInput(limit=100), repository=repository)
    count = await repository.mark_notifications_read_all(actor_id, [item["id"] for item in notifications])
    await _audit(actor_id, "admin.notifications.read_all", "notification", metadata={"count": count})
    return {"count": count, "before": input_data.before}


async def list_admin_support_services(actor_id: str, query: SupportServicesQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    filters = {"deletedAt": {"$exists": False}}
    for key, value in query.model_dump(exclude_none=True).items():
        filters[key] = value
    rows = await repository.list_support_services(filters)
    await _audit(actor_id, "admin.support_services.list", "support_service", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def create_admin_support_service(actor_id: str, input_data: SupportServiceInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.create_support_service(input_data.model_dump(exclude_none=True))
    await _audit(actor_id, "admin.support_services.create", "support_service", str(record["_id"]))
    return _serialize(record)


async def update_admin_support_service(actor_id: str, service_id: str, input_data: UpdateSupportServiceInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.update_support_service(service_id, input_data.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Support service not found")
    await _audit(actor_id, "admin.support_services.update", "support_service", service_id)
    return _serialize(record)


async def delete_admin_support_service(actor_id: str, service_id: str, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.delete_support_service(service_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Support service not found")
    await _audit(actor_id, "admin.support_services.delete", "support_service", service_id)
    return _serialize(record)


async def list_admin_warm_referrals(actor_id: str, query: WarmReferralsQueryInput, *, repository: AdminRepository | None = None) -> list[dict[str, Any]]:
    repository = repository or get_admin_repository()
    filters = {}
    if query.status:
        filters["status"] = query.status
    if query.serviceId:
        filters["serviceId"] = query.serviceId
    rows = await repository.list_warm_referrals(filters, query.limit)
    await _audit(actor_id, "admin.warm_referrals.list", "warm_referral", metadata={"count": len(rows)})
    return [_serialize(row) for row in rows]


async def update_admin_warm_referral(actor_id: str, referral_id: str, input_data: UpdateWarmReferralInput, *, repository: AdminRepository | None = None) -> dict[str, Any]:
    repository = repository or get_admin_repository()
    record = await repository.update_warm_referral(referral_id, input_data.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Warm referral not found")
    await _audit(actor_id, "admin.warm_referrals.update", "warm_referral", referral_id, {"status": input_data.status})
    return _serialize(record)
