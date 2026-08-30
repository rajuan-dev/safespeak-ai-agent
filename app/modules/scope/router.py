from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.responses import success
from app.modules.auth.dependencies import require_admin_role
from app.modules.profiles.service import (
    get_community_profile_options,
    get_cultural_profile_options,
    get_faith_profile_options,
    get_language_options,
)

router = APIRouter(prefix="/scope", tags=["scope"])

SAFE_SPEAK_JURISDICTIONS = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
SAFE_SPEAK_CONSENT_FLAGS = [
    "store_locally",
    "cloud_sync",
    "share_with_agencies",
    "use_anonymised_analytics",
    "process_with_ai",
    "transcribe_audio",
    "warm_referral",
    "manual_location",
]
SAFE_SPEAK_DESTINATION_TYPES = [
    "police",
    "anti_discrimination_agency",
    "esafety",
    "legal_aid",
    "community_legal_centre",
    "education_provider",
    "workplace_channel",
    "scamwatch",
    "reportcyber",
    "community_support_org",
]
SAFE_SPEAK_DESTINATION_CHANNELS = [
    "api_oauth",
    "api_mtls",
    "secure_email_pgp",
    "secure_email",
    "manual_export_pdf",
    "manual_export_json",
    "booking_link",
]
SAFE_SPEAK_REPORT_STATUSES = ["draft", "local_only", "ready_for_review", "submitted", "received", "closed", "info_only", "withdrawn", "deleted"]
SAFE_SPEAK_SCAM_ANALYSIS_TYPES = ["text", "email", "screenshot", "url"]
SAFE_SPEAK_MICRO_EDUCATION_CATEGORIES = [
    "school_bullying",
    "racial_abuse_at_school",
    "online_harassment",
    "platform_reporting",
    "workplace_misconduct",
    "nsw_racial_hatred_offence",
    "interpreter_use",
    "scams_101",
]
SAFE_SPEAK_ANALYTICS_POLICY = {
    "minimumCellSuppression": 5,
    "requiresDifferentialPrivacyForExternalExports": True,
    "aggregationLevel": "LGA",
    "timeBuckets": ["weekly", "monthly"],
}


async def _bootstrap() -> dict:
    languages = await get_language_options()
    cultural = await get_cultural_profile_options()
    faith = await get_faith_profile_options()
    community = await get_community_profile_options()
    return {
        "scopeVersion": "2026-05-12-scope-alignment-v1",
        "jurisdictions": SAFE_SPEAK_JURISDICTIONS,
        "languages": languages,
        "culturalProfiles": cultural,
        "faithProfiles": faith,
        "communityProfiles": community,
        "culturalProfileGuidance": [],
        "consentFlags": SAFE_SPEAK_CONSENT_FLAGS,
        "incidentTypes": [],
        "supportNeeds": [],
        "destinationTypes": SAFE_SPEAK_DESTINATION_TYPES,
        "destinationChannels": SAFE_SPEAK_DESTINATION_CHANNELS,
        "reportStatuses": SAFE_SPEAK_REPORT_STATUSES,
        "scamAnalysisTypes": SAFE_SPEAK_SCAM_ANALYSIS_TYPES,
        "microEducationCategories": SAFE_SPEAK_MICRO_EDUCATION_CATEGORIES,
        "analyticsPolicy": SAFE_SPEAK_ANALYTICS_POLICY,
        "taxonomies": None,
    }


@router.get("/bootstrap")
async def scope_bootstrap_route():
    return success("Scope bootstrap retrieved", {"bootstrap": await _bootstrap()})


@router.get("/cultural-profiles")
async def scope_cultural_profiles_route():
    return success(
        "Public cultural profiles retrieved",
        {"culturalProfiles": await get_cultural_profile_options()},
    )


@router.get("/blueprint")
async def scope_blueprint_route(
    principal: Annotated[object, Depends(require_admin_role())]
):
    bootstrap = await _bootstrap()
    bootstrap["entities"] = {
        "report": {"requiredFields": ["language", "jurisdiction", "originalNarrative", "status"]},
        "evidenceAsset": {"requiredFields": ["reportId", "type", "mimeType", "sha256Hash", "status"]},
    }
    return success("Scope blueprint retrieved", {"blueprint": bootstrap})
