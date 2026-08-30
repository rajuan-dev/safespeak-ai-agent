from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .model import (
    ADVOCATE_AVAILABILITIES,
    SUPPORT_ISSUE_TYPES,
    SUPPORT_RESOURCE_RISK_LEVELS,
    SUPPORT_RESOURCE_TYPES,
    SUPPORT_SERVICE_TYPES,
)


def _string_list(value: list[str] | None) -> list[str]:
    return value or []


class ServicesQueryInput(BaseModel):
    type: str | None = None
    resource_type: str | None = Field(default=None, alias="resourceType")
    issue_type: str | None = Field(default=None, alias="issueType")
    jurisdiction: str | None = None
    language: str | None = None
    region: str | None = None
    eligibility: str | None = None
    profile: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class AdvocateQueryInput(BaseModel):
    language: str | None = None
    region: str | None = None
    issue_type: str | None = Field(default=None, alias="issueType")
    cultural_profile: str | None = Field(default=None, alias="culturalProfile")
    faith_profile: str | None = Field(default=None, alias="faithProfile")
    availability: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class RecommendationsInput(BaseModel):
    report_id: str | None = Field(default=None, alias="reportId", min_length=24, max_length=24)
    needs: list[str] = Field(default_factory=list)
    resource_types: list[str] = Field(default_factory=list, alias="resourceTypes")
    issue_type: str | None = Field(default=None, alias="issueType")
    safety_risk_level: str | None = Field(default=None, alias="safetyRiskLevel")
    jurisdiction: str | None = None
    region: str | None = None
    eligibility: str | None = None
    profile: str | None = None
    language: str = "en"

    model_config = ConfigDict(populate_by_name=True)


class WarmReferralSummaryInput(BaseModel):
    incident_summary: str | None = Field(default=None, alias="incidentSummary", max_length=1000)
    immediate_safety_concerns: str | None = Field(
        default=None, alias="immediateSafetyConcerns", max_length=600
    )
    preferred_contact_method: str | None = Field(
        default=None, alias="preferredContactMethod", max_length=120
    )
    interpreter_preference: str | None = Field(
        default=None, alias="interpreterPreference", max_length=120
    )
    cultural_context: str | None = Field(default=None, alias="culturalContext", max_length=600)
    information_only_disclaimer: bool = Field(default=True, alias="informationOnlyDisclaimer")

    model_config = ConfigDict(populate_by_name=True)


class WarmReferralInput(BaseModel):
    service_id: str = Field(alias="serviceId", min_length=1, max_length=120)
    contact_preference: str = Field(alias="contactPreference")
    safe_contact: str = Field(alias="safeContact", min_length=1, max_length=320)
    notes: str | None = Field(default=None, max_length=4000)
    minimal_summary: WarmReferralSummaryInput | None = Field(
        default=None, alias="minimalSummary"
    )
    included_fields: list[str] = Field(default_factory=list, alias="includedFields")
    share_profile_context: bool = Field(default=False, alias="shareProfileContext")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class AdvocateRequestInput(BaseModel):
    advocate_type: str = Field(alias="advocateType", min_length=1, max_length=120)
    advocate_profile_id: str | None = Field(
        default=None, alias="advocateProfileId", min_length=24, max_length=24
    )
    advocate_key: str | None = Field(default=None, alias="advocateKey", max_length=120)
    language: str = "en"
    issue_type: str | None = Field(default=None, alias="issueType")
    region: str | None = None
    safe_contact_preference: str = Field(
        default="in_app", alias="safeContactPreference"
    )
    notes: str | None = Field(default=None, max_length=4000)
    confirmation_copy: str | None = Field(default=None, alias="confirmationCopy", max_length=1000)

    model_config = ConfigDict(populate_by_name=True)


class OwnedAdvocateRequestQueryInput(BaseModel):
    status: str | None = None
    active_only: bool | None = Field(default=None, alias="activeOnly")
    limit: int = 20

    model_config = ConfigDict(populate_by_name=True)


class CancelAdvocateRequestInput(BaseModel):
    reason_code: str = Field(default="user_cancelled", alias="reasonCode", max_length=80)

    model_config = ConfigDict(populate_by_name=True)


class HelpSupportRequestInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=4000)


class SafetyPlanInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    trusted_contacts: list[dict[str, Any]] = Field(default_factory=list, alias="trustedContacts")
    safe_places: list[str] = Field(default_factory=list, alias="safePlaces")
    warning_signs: list[str] = Field(default_factory=list, alias="warningSigns")
    coping_strategies: list[str] = Field(default_factory=list, alias="copingStrategies")
    emergency_steps: list[str] = Field(default_factory=list, alias="emergencySteps")
    is_active: bool = Field(default=True, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class UpdateSafetyPlanInput(SafetyPlanInput):
    title: str | None = None
    trusted_contacts: list[dict[str, Any]] | None = Field(default=None, alias="trustedContacts")
    safe_places: list[str] | None = Field(default=None, alias="safePlaces")
    warning_signs: list[str] | None = Field(default=None, alias="warningSigns")
    coping_strategies: list[str] | None = Field(default=None, alias="copingStrategies")
    emergency_steps: list[str] | None = Field(default=None, alias="emergencySteps")
    is_active: bool | None = Field(default=None, alias="isActive")


def _validate_enum(value: str | None, choices: set[str], label: str) -> str | None:
    if value is None:
        return value
    if value not in choices:
        raise ValueError(f"Invalid {label}")
    return value

ServicesQueryInput.validate_type = field_validator("type")(  # type: ignore[attr-defined]
    classmethod(
        lambda cls, value: _validate_enum(
            value, SUPPORT_SERVICE_TYPES, "support service type"
        )
    )
)
ServicesQueryInput.validate_resource_type = field_validator("resource_type")(  # type: ignore[attr-defined]
    classmethod(
        lambda cls, value: _validate_enum(
            value, SUPPORT_RESOURCE_TYPES, "support resource type"
        )
    )
)
ServicesQueryInput.validate_issue_type = field_validator("issue_type")(  # type: ignore[attr-defined]
    classmethod(lambda cls, value: _validate_enum(value, SUPPORT_ISSUE_TYPES, "support issue type"))
)
AdvocateQueryInput.validate_issue_type = field_validator("issue_type")(  # type: ignore[attr-defined]
    classmethod(lambda cls, value: _validate_enum(value, SUPPORT_ISSUE_TYPES, "support issue type"))
)
AdvocateQueryInput.validate_availability = field_validator("availability")(  # type: ignore[attr-defined]
    classmethod(
        lambda cls, value: _validate_enum(
            value, ADVOCATE_AVAILABILITIES, "advocate availability"
        )
    )
)
RecommendationsInput.validate_issue_type = field_validator("issue_type")(  # type: ignore[attr-defined]
    classmethod(lambda cls, value: _validate_enum(value, SUPPORT_ISSUE_TYPES, "support issue type"))
)
RecommendationsInput.validate_safety_risk_level = field_validator("safety_risk_level")(  # type: ignore[attr-defined]
    classmethod(
        lambda cls, value: _validate_enum(
            value, SUPPORT_RESOURCE_RISK_LEVELS, "support resource risk level"
        )
    )
)


@field_validator("contact_preference")
@classmethod
def _validate_contact_preference(cls, value: str) -> str:
    if value not in {"phone", "email", "in_app"}:
        raise ValueError("Invalid contact preference")
    return value


WarmReferralInput.validate_contact_preference = _validate_contact_preference  # type: ignore[attr-defined]


@field_validator("safe_contact_preference")
@classmethod
def _validate_safe_contact_preference(cls, value: str) -> str:
    if value not in {"phone", "email", "in_app", "no_direct_contact"}:
        raise ValueError("Invalid safe contact preference")
    return value


AdvocateRequestInput.validate_safe_contact_preference = _validate_safe_contact_preference  # type: ignore[attr-defined]
