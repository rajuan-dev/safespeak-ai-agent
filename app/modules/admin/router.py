from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config.database import get_database
from app.core.responses import success

from .dependencies import (
    AnalyticsPrincipal,
    ContentAdminPrincipal,
    CurrentAdminPrincipal,
    IntegrationAdminPrincipal,
    SuperAdminPrincipal,
    SupportServiceAdminPrincipal,
)
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
from .service import (
    create_admin_destination,
    create_admin_submission_template,
    create_admin_support_service,
    create_admin_user,
    delete_admin_support_service,
    get_admin_ai_engine_overview,
    get_admin_dashboard,
    get_admin_data_protection_overview,
    get_admin_intelligence_center_overview,
    get_admin_language_packs_overview,
    get_admin_platform_health,
    list_admin_destinations,
    list_admin_educational_content,
    list_admin_knowledge_sources,
    list_admin_notifications,
    list_admin_privacy_requests,
    list_admin_report_deliveries,
    list_admin_submission_templates,
    list_admin_support_services,
    list_admin_users,
    list_admin_warm_referrals,
    mark_admin_notification_read,
    mark_admin_notifications_read_all,
    update_admin_destination,
    update_admin_privacy_request,
    update_admin_submission_template,
    update_admin_support_service,
    update_admin_user,
    update_admin_warm_referral,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class CulturalProfileInput(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    communityType: str = Field(min_length=1, max_length=40)
    languages: list[str] = Field(default_factory=list)
    faithPathway: str | None = Field(default=None, max_length=240)
    responseGuidance: str = Field(min_length=1, max_length=2500)
    referralPreferences: list[str] = Field(default_factory=list)
    contentGuidance: list[str] = Field(default_factory=list)
    validationStatus: str = Field(default="draft", min_length=1, max_length=40)
    reviewCadence: str = Field(default="Quarterly partner review", min_length=1, max_length=160)
    partnerReviewRequired: bool = True
    isActive: bool = True
    metadata: dict[str, Any] | None = None


class CulturalProfileUpdateInput(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=240)
    communityType: str | None = Field(default=None, min_length=1, max_length=40)
    languages: list[str] | None = None
    faithPathway: str | None = Field(default=None, max_length=240)
    responseGuidance: str | None = Field(default=None, min_length=1, max_length=2500)
    referralPreferences: list[str] | None = None
    contentGuidance: list[str] | None = None
    validationStatus: str | None = Field(default=None, min_length=1, max_length=40)
    reviewCadence: str | None = Field(default=None, min_length=1, max_length=160)
    partnerReviewRequired: bool | None = None
    isActive: bool | None = None
    metadata: dict[str, Any] | None = None


def _cultural_profiles():
    return get_database()["adminculturalprofiles"]


def _serialize_cultural_profile(document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload["_id"] = str(payload["_id"])
    for field_name in ("createdAt", "updatedAt", "reviewedAt"):
        value = payload.get(field_name)
        if value is not None:
            payload[field_name] = value.isoformat() if hasattr(value, "isoformat") else value
    if payload.get("reviewedBy") is not None:
        payload["reviewedBy"] = str(payload["reviewedBy"])
    return payload


def _advocate_profiles():
    return get_database()["advocateprofiles"]


def _serialize_advocate_profile(document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload["_id"] = str(payload["_id"])
    for field_name in ("createdAt", "updatedAt"):
        value = payload.get(field_name)
        if value is not None:
            payload[field_name] = value.isoformat() if hasattr(value, "isoformat") else value
    return payload


async def _get_advocate_profile_or_404(profile_id: str) -> dict[str, Any]:
    if not ObjectId.is_valid(profile_id):
        raise HTTPException(status_code=404, detail="Advocate profile not found")
    profile = await _advocate_profiles().find_one({"_id": ObjectId(profile_id)})
    if not profile:
        raise HTTPException(status_code=404, detail="Advocate profile not found")
    return profile


async def _get_cultural_profile_or_404(profile_id: str) -> dict[str, Any]:
    if not ObjectId.is_valid(profile_id):
        raise HTTPException(status_code=404, detail="Cultural profile not found")
    profile = await _cultural_profiles().find_one(
        {"_id": ObjectId(profile_id), "deletedAt": {"$exists": False}}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Cultural profile not found")
    return profile


@router.get("/dashboard")
async def admin_dashboard_route(principal: CurrentAdminPrincipal):
    dashboard = await get_admin_dashboard()
    return success("Admin dashboard retrieved", {"dashboard": dashboard})


@router.get("/notifications")
async def admin_notifications_route(principal: SuperAdminPrincipal, query: NotificationsQueryInput = None):
    notifications = await list_admin_notifications(principal.user_id or "", query or NotificationsQueryInput())
    return success("Admin notifications retrieved", {"notifications": notifications})


@router.post("/notifications/read")
async def admin_notifications_read_route(input_data: NotificationReadInput, principal: SuperAdminPrincipal):
    read_receipt = await mark_admin_notification_read(principal.user_id or "", input_data)
    return success("Admin notifications marked read", {"readReceipt": read_receipt})


@router.post("/notifications/read-all")
async def admin_notifications_read_all_route(input_data: NotificationReadAllInput, principal: SuperAdminPrincipal):
    read_receipt = await mark_admin_notifications_read_all(principal.user_id or "", input_data)
    return success("Admin notifications marked read", {"readReceipt": read_receipt})


@router.get("/users")
async def admin_users_route(principal: SuperAdminPrincipal, query: UsersQueryInput = None):
    users = await list_admin_users(principal.user_id or "", query or UsersQueryInput())
    return success("Admin users retrieved", {"users": users})


@router.post("/users")
async def create_admin_user_route(input_data: CreateAdminUserInput, principal: SuperAdminPrincipal):
    user = await create_admin_user(principal.user_id or "", input_data)
    return success("Admin user created", {"user": user})


@router.patch("/users/{id}")
async def update_admin_user_route(id: str, input_data: UpdateAdminUserInput, principal: SuperAdminPrincipal):
    user = await update_admin_user(principal.user_id or "", id, input_data)
    return success("Admin user updated", {"user": user})


@router.get("/cultural-profiles/overview")
async def admin_cultural_profiles_overview_route(principal: CurrentAdminPrincipal):
    base_filter = {"deletedAt": {"$exists": False}}
    collection = _cultural_profiles()
    total = await collection.count_documents(base_filter)
    validated = await collection.count_documents({**base_filter, "validationStatus": "validated"})
    pending_review = await collection.count_documents({**base_filter, "validationStatus": "pending_review"})
    needs_update = await collection.count_documents({**base_filter, "validationStatus": "needs_update"})
    archived = await collection.count_documents({**base_filter, "validationStatus": "archived"})
    partner_review = await collection.count_documents({**base_filter, "partnerReviewRequired": True})
    by_type = {
        "cultural": await collection.count_documents({**base_filter, "communityType": "cultural"}),
        "faith": await collection.count_documents({**base_filter, "communityType": "faith"}),
        "community": await collection.count_documents({**base_filter, "communityType": "community"}),
    }
    return success(
        "Admin cultural profiles overview retrieved",
        {
            "culturalProfiles": {
                "total": total,
                "validated": validated,
                "pendingReview": pending_review,
                "needsUpdate": needs_update,
                "archived": archived,
                "partnerReviewRequired": partner_review,
                "byCommunityType": by_type,
            }
        },
    )


@router.get("/cultural-profiles")
async def admin_cultural_profiles_route(
    principal: ContentAdminPrincipal,
    communityType: str | None = None,
    validationStatus: str | None = None,
    isActive: bool | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    query: dict[str, Any] = {"deletedAt": {"$exists": False}}
    if communityType:
        query["communityType"] = communityType
    if validationStatus:
        query["validationStatus"] = validationStatus
    if isActive is not None:
        query["isActive"] = isActive
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"key": {"$regex": search, "$options": "i"}},
            {"responseGuidance": {"$regex": search, "$options": "i"}},
        ]
    cursor = _cultural_profiles().find(query).sort([("communityType", 1), ("name", 1)]).limit(limit)
    profiles = [_serialize_cultural_profile(item) for item in await cursor.to_list(length=limit)]
    return success("Admin cultural profiles retrieved", {"culturalProfiles": profiles})


@router.post("/cultural-profiles")
async def create_admin_cultural_profile_route(
    input_data: CulturalProfileInput,
    principal: ContentAdminPrincipal,
):
    now = datetime.now(UTC)
    payload = input_data.model_dump(exclude_none=True)
    payload.update({"createdAt": now, "updatedAt": now})
    if payload.get("validationStatus") == "validated":
        payload["reviewedAt"] = now
        if principal.user_id and ObjectId.is_valid(principal.user_id):
            payload["reviewedBy"] = ObjectId(principal.user_id)
    result = await _cultural_profiles().insert_one(payload)
    profile = await _cultural_profiles().find_one({"_id": result.inserted_id})
    return success("Admin cultural profile created", {"culturalProfile": _serialize_cultural_profile(profile)})


@router.patch("/cultural-profiles/{id}")
async def update_admin_cultural_profile_route(
    id: str,
    input_data: CulturalProfileUpdateInput,
    principal: ContentAdminPrincipal,
):
    profile = await _get_cultural_profile_or_404(id)
    updates = input_data.model_dump(exclude_none=True)
    updates["updatedAt"] = datetime.now(UTC)
    if updates.get("validationStatus") == "validated" and profile.get("validationStatus") != "validated":
        updates["reviewedAt"] = updates["updatedAt"]
        if principal.user_id and ObjectId.is_valid(principal.user_id):
            updates["reviewedBy"] = ObjectId(principal.user_id)
    await _cultural_profiles().update_one({"_id": profile["_id"]}, {"$set": updates})
    updated = await _cultural_profiles().find_one({"_id": profile["_id"]})
    return success("Admin cultural profile updated", {"culturalProfile": _serialize_cultural_profile(updated)})


@router.delete("/cultural-profiles/{id}")
async def delete_admin_cultural_profile_route(
    id: str,
    principal: ContentAdminPrincipal,
):
    profile = await _get_cultural_profile_or_404(id)
    await _cultural_profiles().update_one(
        {"_id": profile["_id"]},
        {"$set": {"deletedAt": datetime.now(UTC), "updatedAt": datetime.now(UTC)}},
    )
    deleted = await _cultural_profiles().find_one({"_id": profile["_id"]})
    return success("Admin cultural profile deleted", {"culturalProfile": _serialize_cultural_profile(deleted)})


@router.get("/advocates")
async def admin_advocates_route(
    principal: SupportServiceAdminPrincipal,
    isActive: bool | None = None,
    isPublished: bool | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    query: dict[str, Any] = {}
    if isActive is not None:
        query["isActive"] = isActive
    if isPublished is not None:
        query["isPublished"] = isPublished
    if search:
        query["$or"] = [
            {"displayName": {"$regex": search, "$options": "i"}},
            {"key": {"$regex": search, "$options": "i"}},
            {"publicBio": {"$regex": search, "$options": "i"}},
        ]
    cursor = _advocate_profiles().find(query).sort("displayName", 1).limit(limit)
    profiles = [_serialize_advocate_profile(item) for item in await cursor.to_list(length=limit)]
    return success("Admin advocates retrieved", {"advocates": profiles})


@router.patch("/advocates/{id}")
async def update_admin_advocate_route(
    id: str,
    payload: dict[str, Any],
    principal: SupportServiceAdminPrincipal,
):
    profile = await _get_advocate_profile_or_404(id)
    updates = {key: value for key, value in payload.items() if key not in {"_id", "createdAt"}}
    updates["updatedAt"] = datetime.now(UTC)
    await _advocate_profiles().update_one({"_id": profile["_id"]}, {"$set": updates})
    updated = await _advocate_profiles().find_one({"_id": profile["_id"]})
    return success("Admin advocate updated", {"advocate": _serialize_advocate_profile(updated)})


@router.get("/destinations")
async def admin_destinations_route(principal: IntegrationAdminPrincipal, query: DestinationsQueryInput = None):
    destinations = await list_admin_destinations(principal.user_id or "", query or DestinationsQueryInput())
    return success("Admin destinations retrieved", {"destinations": destinations})


@router.post("/destinations")
async def create_admin_destination_route(input_data: DestinationInput, principal: IntegrationAdminPrincipal):
    destination = await create_admin_destination(principal.user_id or "", input_data)
    return success("Admin destination created", {"destination": destination})


@router.patch("/destinations/{id}")
async def update_admin_destination_route(id: str, input_data: UpdateDestinationInput, principal: IntegrationAdminPrincipal):
    destination = await update_admin_destination(principal.user_id or "", id, input_data)
    return success("Admin destination updated", {"destination": destination})


@router.get("/submission-templates")
async def admin_submission_templates_route(principal: IntegrationAdminPrincipal, query: SubmissionTemplatesQueryInput = None):
    templates = await list_admin_submission_templates(principal.user_id or "", query or SubmissionTemplatesQueryInput())
    return success("Admin submission templates retrieved", {"templates": templates})


@router.post("/submission-templates")
async def create_admin_submission_template_route(input_data: SubmissionTemplateInput, principal: IntegrationAdminPrincipal):
    template = await create_admin_submission_template(principal.user_id or "", input_data)
    return success("Admin submission template created", {"template": template})


@router.patch("/submission-templates/{id}")
async def update_admin_submission_template_route(id: str, input_data: UpdateSubmissionTemplateInput, principal: IntegrationAdminPrincipal):
    template = await update_admin_submission_template(principal.user_id or "", id, input_data)
    return success("Admin submission template updated", {"template": template})


@router.get("/report-deliveries")
async def admin_report_deliveries_route(principal: IntegrationAdminPrincipal, query: ReportDeliveriesQueryInput = None):
    deliveries = await list_admin_report_deliveries(principal.user_id or "", query or ReportDeliveriesQueryInput())
    return success("Admin report deliveries retrieved", {"deliveries": deliveries})


@router.get("/knowledge-sources")
async def admin_knowledge_sources_route(principal: ContentAdminPrincipal):
    sources = await list_admin_knowledge_sources(principal.user_id or "")
    return success("Admin knowledge sources retrieved", {"knowledgeSources": sources})


@router.get("/educational-content")
async def admin_educational_content_route(principal: ContentAdminPrincipal):
    content = await list_admin_educational_content(principal.user_id or "")
    return success("Admin educational content retrieved", content)


@router.get("/data-protection/overview")
async def admin_data_protection_overview_route(principal: SuperAdminPrincipal):
    overview = await get_admin_data_protection_overview(principal.user_id or "")
    return success("Admin data protection overview retrieved", {"overview": overview})


@router.get("/ai-engine/overview")
async def admin_ai_engine_overview_route(principal: ContentAdminPrincipal):
    overview = await get_admin_ai_engine_overview(principal.user_id or "")
    return success("Admin AI engine overview retrieved", {"overview": overview})


@router.get("/language-packs/overview")
async def admin_language_packs_overview_route(principal: ContentAdminPrincipal):
    overview = await get_admin_language_packs_overview(principal.user_id or "")
    return success("Admin language packs overview retrieved", {"overview": overview})


@router.get("/insights/incident-insights/overview")
async def admin_incident_insights_overview_route(principal: AnalyticsPrincipal):
    overview = await get_admin_intelligence_center_overview(principal.user_id or "")
    return success("Admin intelligence center overview retrieved", {"overview": overview})


@router.get("/platform-health")
async def admin_platform_health_route(principal: AnalyticsPrincipal):
    platform_health = await get_admin_platform_health(principal.user_id or "")
    return success("Admin platform health retrieved", {"platformHealth": platform_health})


@router.get("/privacy-requests")
async def admin_privacy_requests_route(principal: SuperAdminPrincipal, query: PrivacyRequestsQueryInput = None):
    privacy_requests = await list_admin_privacy_requests(principal.user_id or "", query or PrivacyRequestsQueryInput())
    return success("Admin privacy requests retrieved", {"privacyRequests": privacy_requests})


@router.patch("/privacy-requests/{id}")
async def update_admin_privacy_request_route(id: str, input_data: UpdatePrivacyRequestInput, principal: SuperAdminPrincipal):
    privacy_request = await update_admin_privacy_request(principal.user_id or "", id, input_data)
    return success("Admin privacy request updated", {"privacyRequest": privacy_request})


@router.get("/support-services")
async def admin_support_services_route(principal: SupportServiceAdminPrincipal, query: SupportServicesQueryInput = None):
    services = await list_admin_support_services(principal.user_id or "", query or SupportServicesQueryInput())
    return success("Admin support services retrieved", {"services": services})


@router.post("/support-services")
async def create_admin_support_service_route(input_data: SupportServiceInput, principal: SupportServiceAdminPrincipal):
    service = await create_admin_support_service(principal.user_id or "", input_data)
    return success("Admin support service created", {"service": service})


@router.patch("/support-services/{id}")
async def update_admin_support_service_route(id: str, input_data: UpdateSupportServiceInput, principal: SupportServiceAdminPrincipal):
    service = await update_admin_support_service(principal.user_id or "", id, input_data)
    return success("Admin support service updated", {"service": service})


@router.delete("/support-services/{id}")
async def delete_admin_support_service_route(id: str, principal: SupportServiceAdminPrincipal):
    service = await delete_admin_support_service(principal.user_id or "", id)
    return success("Admin support service deleted", {"service": service})


@router.get("/support-services/warm-referrals")
async def admin_warm_referrals_route(principal: SupportServiceAdminPrincipal, query: WarmReferralsQueryInput = None):
    referrals = await list_admin_warm_referrals(principal.user_id or "", query or WarmReferralsQueryInput())
    return success("Admin warm referrals retrieved", {"referrals": referrals})


@router.patch("/support-services/warm-referrals/{id}")
async def update_admin_warm_referral_route(id: str, input_data: UpdateWarmReferralInput, principal: SupportServiceAdminPrincipal):
    referral = await update_admin_warm_referral(principal.user_id or "", id, input_data)
    return success("Admin warm referral updated", {"referral": referral})
