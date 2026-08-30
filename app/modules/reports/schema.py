from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .model import ANONYMITY_MODES, REPORT_STATUSES, SEVERITIES, STRUCTURED_FIELD_KEYS


def _normalize_object(value: dict[str, Any] | None) -> dict[str, Any]:
    return value or {}


class CreateReportInput(BaseModel):
    language: str = "en"
    jurisdiction: str = "NSW"
    lga: str | None = None
    context: str | None = None
    original_narrative: str | None = Field(default=None, alias="originalNarrative")
    translated_narrative: str | None = Field(default=None, alias="translatedNarrative")
    incident_type: str | None = Field(default=None, alias="incidentType")
    severity: str | None = None
    structured_fields: dict[str, Any] = Field(default_factory=dict, alias="structuredFields")
    status: str = "draft"

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @field_validator("structured_fields")
    @classmethod
    def validate_structured_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        payload = _normalize_object(value)
        invalid_keys = [key for key in payload if key not in STRUCTURED_FIELD_KEYS]
        if invalid_keys:
            raise ValueError(f"Invalid structured fields: {', '.join(invalid_keys)}")
        return payload

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str | None) -> str | None:
        if value is None or value in SEVERITIES:
            return value
        raise ValueError("Invalid severity")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in REPORT_STATUSES:
            raise ValueError("Invalid report status")
        return value


class UpdateReportInput(CreateReportInput):
    language: str | None = None
    jurisdiction: str | None = None
    status: str | None = None


class SubmissionPreviewInput(BaseModel):
    destination_ids: list[str] = Field(alias="destinationIds", min_length=1)
    anonymity_mode: str = Field(default="identified", alias="anonymityMode")
    notes: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("anonymity_mode")
    @classmethod
    def validate_anonymity_mode(cls, value: str) -> str:
        if value not in ANONYMITY_MODES:
            raise ValueError("Invalid anonymity mode")
        return value


class CreateSubmissionInput(BaseModel):
    destination_id: str = Field(alias="destinationId", min_length=24, max_length=24)
    anonymity_mode: str = Field(default="identified", alias="anonymityMode")
    notes: str | None = None
    confirm_consent: bool = Field(alias="confirmConsent")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("anonymity_mode")
    @classmethod
    def validate_anonymity_mode(cls, value: str) -> str:
        if value not in ANONYMITY_MODES:
            raise ValueError("Invalid anonymity mode")
        return value

    @field_validator("confirm_consent")
    @classmethod
    def validate_confirm_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Submission consent confirmation is required")
        return value


class AcknowledgeSubmissionInput(BaseModel):
    status: str = "acknowledged"
    external_reference: str = Field(alias="externalReference", min_length=1)
    acknowledgement_message: str | None = Field(default=None, alias="acknowledgementMessage")
    acknowledgement_payload: dict[str, Any] = Field(
        default_factory=dict, alias="acknowledgementPayload"
    )

    model_config = ConfigDict(populate_by_name=True)


class MarkInfoOnlyInput(BaseModel):
    reason: str | None = None


class WithdrawReportInput(BaseModel):
    reason: str | None = None


class RequestDeleteInput(BaseModel):
    reason: str | None = None
