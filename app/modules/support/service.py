from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.modules.audit.service import create_audit_log
from app.modules.consent.service import get_current_consent

from .matching import build_advocate_query, build_service_query, matches_recommendation
from .model import DEFAULT_SUPPORT_SERVICES, LEGACY_ADVOCATE_PROFILES, SUPPORT_ACTIONS
from .repository import SupportRepository, get_support_repository
from .routing import active_statuses, assert_advocate_request_transition
from .schema import (
    AdvocateQueryInput,
    AdvocateRequestInput,
    CancelAdvocateRequestInput,
    HelpSupportRequestInput,
    OwnedAdvocateRequestQueryInput,
    RecommendationsInput,
    SafetyPlanInput,
    ServicesQueryInput,
    UpdateSafetyPlanInput,
    WarmReferralInput,
)


def _owner_filter(owner: dict[str, str | None]) -> dict[str, str]:
    if owner.get("userId"):
        return {"userId": owner["userId"]}
    if owner.get("sessionId"):
        return {"sessionId": owner["sessionId"]}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "binary"):
        return str(value)
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    payload = {key: _serialize_value(value) for key, value in document.items()}
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
    for key in (
        "userId",
        "sessionId",
        "assignedAdvocateProfileId",
        "advocateProfileId",
        "assignedBy",
    ):
        if payload.get(key) is not None:
            payload[key] = str(payload[key])
    return payload


def _public_service_record(document: dict[str, Any]) -> dict[str, Any]:
    record = _serialize_document(document)
    record["id"] = record.get("key") or record.get("_id")
    record["url"] = record.get("websiteUrl")
    return record


def _public_advocate_record(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("key")),
        "key": document.get("key"),
        "advocateType": document.get("key"),
        "displayName": document.get("displayName"),
        "description": document.get("publicBio"),
        "publicBio": document.get("publicBio"),
        "languages": document.get("languages") or [],
        "issueTypes": document.get("issueTypes") or [],
        "regions": document.get("regions") or [],
        "culturalProfiles": document.get("culturalProfiles") or [],
        "faithProfiles": document.get("faithProfiles") or [],
        "availability": document.get("availability"),
        "informationOnly": True,
    }


def _advocate_snapshot(document: dict[str, Any]) -> dict[str, Any]:
    public = _public_advocate_record(document)
    return {
        "key": public["key"],
        "displayName": public["displayName"],
        "publicBio": public["publicBio"],
        "languages": public["languages"],
        "issueTypes": public["issueTypes"],
        "regions": public["regions"],
        "culturalProfiles": public["culturalProfiles"],
        "faithProfiles": public["faithProfiles"],
        "availability": public["availability"],
    }


def _mask_safe_contact(value: str | None) -> str | None:
    if not value:
        return None
    if "@" in value:
        name, domain = value.split("@", 1)
        return f"{name[:2]}***@{domain}"
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 4:
        return f"***{digits[-4:]}"
    return "***"


def _reference_from_id(value: str) -> str:
    return f"ADV-{value[-8:].upper()}"


async def _audit(
    context: dict[str, Any],
    action: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    owner = context["owner"]
    await create_audit_log(
        actor_type="user" if owner.get("userId") else "anonymous_session",
        actor_id=owner.get("userId"),
        session_id=owner.get("sessionId"),
        action=action,
        resource_type="system",
        resource_id=resource_id,
        ip=context.get("ip"),
        user_agent=context.get("userAgent"),
        metadata=metadata or {},
    )


async def _ensure_seed(repository: SupportRepository) -> None:
    for service in DEFAULT_SUPPORT_SERVICES:
        await repository.seed_support_service(service)
    for profile in LEGACY_ADVOCATE_PROFILES:
        await repository.seed_advocate_profile(profile)


async def _assert_warm_referral_consent(owner: dict[str, str | None]) -> None:
    consent = await get_current_consent(owner)
    if not consent.get("warm_referral"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "warm_referral consent is required")


async def _assert_advocate_request_consent(owner: dict[str, str | None]) -> None:
    consent = await get_current_consent(owner)
    if not consent.get("advocate_request"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "advocate_request consent is required")


async def list_support_services(
    context: dict[str, Any],
    query: ServicesQueryInput,
    *,
    repository: SupportRepository | None = None,
) -> list[dict[str, Any]]:
    _owner_filter(context["owner"])
    repository = repository or get_support_repository()
    await _ensure_seed(repository)
    services = await repository.list_support_services(build_service_query(query))
    serialized = [_public_service_record(item) for item in services]
    await _audit(context, SUPPORT_ACTIONS["servicesList"], metadata={"count": len(serialized)})
    return serialized


async def get_support_service_by_id(
    context: dict[str, Any],
    service_id: str,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    _owner_filter(context["owner"])
    repository = repository or get_support_repository()
    await _ensure_seed(repository)
    query = {
        "deletedAt": {"$exists": False},
        "isPublished": True,
        "isActive": True,
        "$or": [{"key": service_id}, {"name": service_id}],
    }
    if ObjectId.is_valid(service_id):
        query["$or"].append({"_id": ObjectId(service_id)})
    service = await repository.find_support_service(query)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Support service not found")
    await _audit(context, SUPPORT_ACTIONS["serviceGet"], metadata={"serviceId": service_id})
    return _public_service_record(service)


async def get_recommendations(
    context: dict[str, Any],
    input_data: RecommendationsInput,
    *,
    repository: SupportRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_support_repository()
    if input_data.report_id:
        report = await repository.find_report_for_owner(context["owner"], input_data.report_id)
        if not report:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    services = await list_support_services(
        context,
        ServicesQueryInput(
            resourceType=input_data.resource_types[0] if input_data.resource_types else None,
            issueType=input_data.issue_type,
            jurisdiction=input_data.jurisdiction,
            language=input_data.language,
            region=input_data.region,
            eligibility=input_data.eligibility,
            profile=input_data.profile,
        ),
        repository=repository,
    )
    filtered = [service for service in services if matches_recommendation(service, input_data)]
    await _audit(
        context,
        SUPPORT_ACTIONS["recommendations"],
        input_data.report_id,
        {"needs": input_data.needs, "count": len(filtered)},
    )
    return filtered


async def create_warm_referral(
    context: dict[str, Any],
    input_data: WarmReferralInput,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_support_repository()
    _owner_filter(context["owner"])
    await _assert_warm_referral_consent(context["owner"])
    service = await get_support_service_by_id(context, input_data.service_id, repository=repository)
    minimal_summary = {
        "incidentSummary": (
            input_data.minimal_summary.incident_summary if input_data.minimal_summary else None
        ),
        "immediateSafetyConcerns": (
            input_data.minimal_summary.immediate_safety_concerns
            if input_data.minimal_summary
            else None
        ),
        "preferredContactMethod": (
            input_data.minimal_summary.preferred_contact_method
            if input_data.minimal_summary and input_data.minimal_summary.preferred_contact_method
            else input_data.contact_preference
        ),
        "interpreterPreference": (
            input_data.minimal_summary.interpreter_preference
            if input_data.minimal_summary
            else None
        ),
        "culturalContext": (
            input_data.minimal_summary.cultural_context
            if input_data.minimal_summary and input_data.share_profile_context
            else None
        ),
        "informationOnlyDisclaimer": True,
    }
    included_fields = (
        input_data.included_fields
        if input_data.included_fields
        else [
            key
            for key, value in minimal_summary.items()
            if value not in (None, "", False)
        ]
    )
    referral = await repository.create_warm_referral(
        {
            **_owner_filter(context["owner"]),
            "serviceId": input_data.service_id,
            "serviceName": service.get("name"),
            "serviceType": service.get("type"),
            "partnerKey": service.get("key") or input_data.service_id,
            "contactPreference": input_data.contact_preference,
            "safeContact": input_data.safe_contact,
            "notes": input_data.notes,
            "minimalSummary": minimal_summary,
            "includedFields": included_fields,
            "shareProfileContext": input_data.share_profile_context,
            "consentSnapshot": {"warm_referral": True, "capturedAt": datetime.now(UTC)},
            "metadata": input_data.metadata,
            "status": "pending",
        }
    )
    await _audit(
        context,
        SUPPORT_ACTIONS["warmReferral"],
        str(referral["_id"]),
        {
            "serviceId": input_data.service_id,
            "includedFields": included_fields,
            "shareProfileContext": input_data.share_profile_context,
        },
    )
    return _serialize_document(referral)


def _build_advocate_facets(profiles: list[dict[str, Any]]) -> dict[str, list[str]]:
    def collect(field: str) -> list[str]:
        values = set()
        for profile in profiles:
            for item in profile.get(field) or []:
                if isinstance(item, str):
                    values.add(item)
        return sorted(values)

    return {
        "languages": collect("languages"),
        "regions": collect("regions"),
        "issueTypes": collect("issueTypes"),
        "culturalProfiles": collect("culturalProfiles"),
        "faithProfiles": collect("faithProfiles"),
        "availability": sorted(
            {
                item.get("availability")
                for item in profiles
                if isinstance(item.get("availability"), str)
            }
        ),
    }


async def list_advocates(
    context: dict[str, Any],
    query: AdvocateQueryInput,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    _owner_filter(context["owner"])
    repository = repository or get_support_repository()
    await _ensure_seed(repository)
    profiles = await repository.list_advocate_profiles(build_advocate_query(query))
    advocates = [_public_advocate_record(item) for item in profiles]
    await _audit(context, SUPPORT_ACTIONS["advocatesList"], metadata={"count": len(advocates)})
    return {"advocates": advocates, "facets": _build_advocate_facets(profiles)}


async def _find_eligible_advocate(
    repository: SupportRepository, input_data: AdvocateRequestInput
) -> dict[str, Any]:
    query = build_advocate_query(
        AdvocateQueryInput(
            language=input_data.language,
            region=input_data.region,
            issueType=input_data.issue_type,
        )
    )
    key = (input_data.advocate_key or input_data.advocate_type).replace("-", "_").lower()
    selector = {"key": key}
    if input_data.advocate_profile_id and ObjectId.is_valid(input_data.advocate_profile_id):
        selector = {"_id": ObjectId(input_data.advocate_profile_id)}
    advocate = await repository.find_advocate_profile({**query, **selector})
    if not advocate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Eligible advocate profile not found")
    return advocate


async def create_advocate_request(
    context: dict[str, Any],
    input_data: AdvocateRequestInput,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_support_repository()
    _owner_filter(context["owner"])
    await _assert_advocate_request_consent(context["owner"])
    await _ensure_seed(repository)
    advocate = await _find_eligible_advocate(repository, input_data)
    duplicate = await repository.find_duplicate_advocate_request(
        context["owner"], advocate["_id"], active_statuses()
    )
    if duplicate:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An active advocate request already exists for this advocate",
        )
    request_id = ObjectId()
    actor_id = (
        ObjectId(context["owner"]["userId"])
        if context["owner"].get("userId") and ObjectId.is_valid(context["owner"]["userId"])
        else (
            ObjectId(context["owner"]["sessionId"])
            if context["owner"].get("sessionId")
            and ObjectId.is_valid(context["owner"]["sessionId"])
            else None
        )
    )
    request = await repository.create_advocate_request(
        {
            "_id": request_id,
            **_owner_filter(context["owner"]),
            "reference": _reference_from_id(str(request_id)),
            "advocateType": advocate["key"],
            "advocateProfileId": advocate["_id"],
            "advocateKey": advocate["key"],
            "advocateSnapshot": _advocate_snapshot(advocate),
            "language": input_data.language,
            "issueType": input_data.issue_type,
            "region": input_data.region,
            "safeContactPreference": input_data.safe_contact_preference,
            "notes": input_data.notes,
            "confirmationCopy": input_data.confirmation_copy,
            "consentSnapshot": {"advocate_request": True, "capturedAt": datetime.now(UTC)},
            "statusHistory": [
                {
                    "status": "pending",
                    "actorType": "user" if context["owner"].get("userId") else "anonymous_session",
                    "actorId": actor_id,
                    "createdAt": datetime.now(UTC),
                }
            ],
            "status": "pending",
        }
    )
    await _audit(
        context,
        SUPPORT_ACTIONS["advocateRequest"],
        str(request["_id"]),
        {
            "advocateType": input_data.advocate_type,
            "issueType": input_data.issue_type,
            "region": input_data.region,
            "safeContactPreference": input_data.safe_contact_preference,
        },
    )
    return _serialize_document(request)


async def list_owned_advocate_requests(
    context: dict[str, Any],
    query: OwnedAdvocateRequestQueryInput,
    *,
    repository: SupportRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_support_repository()
    filters: dict[str, Any] = {}
    if query.status:
        filters["status"] = query.status
    if query.active_only:
        filters["status"] = {"$in": active_statuses()}
    requests = await repository.list_owned_advocate_requests(context["owner"], filters, query.limit)
    await _audit(
        context,
        SUPPORT_ACTIONS["advocateRequest"],
        metadata={"operation": "list_owned", "count": len(requests)},
    )
    return [_serialize_document(item) for item in requests]


async def get_owned_advocate_request(
    context: dict[str, Any],
    request_id: str,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_support_repository()
    request = await repository.find_owned_advocate_request(context["owner"], request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Advocate request not found")
    return _serialize_document(request)


async def cancel_owned_advocate_request(
    context: dict[str, Any],
    request_id: str,
    input_data: CancelAdvocateRequestInput,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_support_repository()
    request = await repository.find_owned_advocate_request(context["owner"], request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Advocate request not found")
    actor_type = "user" if context["owner"].get("userId") else "anonymous_session"
    assert_advocate_request_transition(request["status"], "cancelled", actor_type)
    history = list(request.get("statusHistory") or [])
    history.append(
        {
            "previousStatus": request["status"],
            "status": "cancelled",
            "actorType": actor_type,
            "actorId": request.get("userId") or request.get("sessionId"),
            "reasonCode": input_data.reason_code or "user_cancelled",
            "createdAt": datetime.now(UTC),
        }
    )
    updated = await repository.update_owned_advocate_request(
        context["owner"],
        request_id,
        {"status": "cancelled", "statusHistory": history},
    )
    await _audit(
        context,
        SUPPORT_ACTIONS["advocateRequest"],
        request_id,
        {
            "operation": "cancel_owned",
            "previousStatus": request["status"],
            "status": "cancelled",
            "reasonCode": input_data.reason_code or "user_cancelled",
        },
    )
    return _serialize_document(updated or request)


async def create_help_support_request(
    context: dict[str, Any],
    input_data: HelpSupportRequestInput,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_support_repository()
    _owner_filter(context["owner"])
    request = await repository.create_help_support_request(
        {
            **_owner_filter(context["owner"]),
            "title": input_data.title,
            "message": input_data.message,
            "status": "pending",
        }
    )
    await _audit(
        context,
        SUPPORT_ACTIONS["helpRequest"],
        str(request["_id"]),
        {"title": input_data.title},
    )
    return _serialize_document(request)


async def list_safety_plans(
    context: dict[str, Any],
    *,
    repository: SupportRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_support_repository()
    plans = await repository.list_safety_plans(context["owner"])
    await _audit(context, SUPPORT_ACTIONS["safetyPlanList"], metadata={"count": len(plans)})
    return [_serialize_document(item) for item in plans]


async def create_safety_plan(
    context: dict[str, Any],
    input_data: SafetyPlanInput,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_support_repository()
    _owner_filter(context["owner"])
    payload = input_data.model_dump(by_alias=True, exclude_none=True)
    plan = await repository.create_safety_plan(
        {**_owner_filter(context["owner"]), **payload}
    )
    await _audit(context, SUPPORT_ACTIONS["safetyPlanCreate"], str(plan["_id"]))
    return _serialize_document(plan)


async def update_safety_plan(
    context: dict[str, Any],
    safety_plan_id: str,
    input_data: UpdateSafetyPlanInput,
    *,
    repository: SupportRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_support_repository()
    updates = input_data.model_dump(by_alias=True, exclude_none=True)
    plan = await repository.update_safety_plan(context["owner"], safety_plan_id, updates)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Safety plan not found")
    await _audit(
        context,
        SUPPORT_ACTIONS["safetyPlanUpdate"],
        safety_plan_id,
        {"changedFields": list(updates.keys())},
    )
    return _serialize_document(plan)
