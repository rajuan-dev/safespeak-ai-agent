from typing import Any


def build_service_query(
    input_data: Any, *, include_publication_filters: bool = True
) -> dict[str, Any]:
    query: dict[str, Any] = {"deletedAt": {"$exists": False}}
    if include_publication_filters:
        query["isPublished"] = True
        query["isActive"] = True
    if getattr(input_data, "type", None):
        query["type"] = input_data.type
    resource_type = getattr(input_data, "resource_type", None)
    if resource_type:
        query["resourceType"] = resource_type
    issue_type = getattr(input_data, "issue_type", None)
    if issue_type:
        query["issueTypes"] = issue_type
    if getattr(input_data, "jurisdiction", None):
        query["jurisdiction"] = input_data.jurisdiction
    if getattr(input_data, "language", None):
        query["languages"] = input_data.language
    if getattr(input_data, "region", None):
        query["regions"] = input_data.region
    if getattr(input_data, "eligibility", None):
        query["eligibility"] = input_data.eligibility
    if getattr(input_data, "profile", None):
        query["$or"] = [
            {"eligibility": input_data.profile},
            {"metadata.profiles": input_data.profile},
        ]
    return query


def matches_recommendation(service: dict[str, Any], input_data: Any) -> bool:
    if input_data.needs and service.get("type") not in input_data.needs:
        return False
    if input_data.resource_types and service.get("resourceType") not in input_data.resource_types:
        return False
    if input_data.issue_type:
        issue_types = service.get("issueTypes") or []
        if input_data.issue_type not in issue_types and "general_support" not in issue_types:
            return False
    if input_data.safety_risk_level:
        levels = service.get("safetyRiskLevels") or []
        if input_data.safety_risk_level not in levels and "all" not in levels:
            return False
    return True


def build_advocate_query(input_data: Any) -> dict[str, Any]:
    query: dict[str, Any] = {
        "deletedAt": {"$exists": False},
        "isPublished": True,
        "isActive": True,
        "optInStatus": "opted_in",
        "vetting.status": "approved",
        "availability": {"$ne": "unavailable"},
    }
    if getattr(input_data, "language", None):
        query["languages"] = input_data.language
    if getattr(input_data, "region", None):
        query["regions"] = {"$in": [input_data.region, "national"]}
    if getattr(input_data, "issue_type", None):
        query["issueTypes"] = {"$in": [input_data.issue_type, "general_support"]}
    if getattr(input_data, "cultural_profile", None):
        query["culturalProfiles"] = input_data.cultural_profile
    if getattr(input_data, "faith_profile", None):
        query["faithProfiles"] = input_data.faith_profile
    if getattr(input_data, "availability", None):
        query["availability"] = input_data.availability
    return query
