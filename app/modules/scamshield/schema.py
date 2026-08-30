import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .model import SCAMSHIELD_ANALYSIS_TYPES, SCAMSHIELD_RISK_LEVELS, SCAMSHIELD_STATUSES


def _object_or_empty(value: dict[str, Any] | None) -> dict[str, Any]:
    return value or {}


class ScamShieldParams(BaseModel):
    id: str = Field(min_length=24, max_length=24)


class AnalyzeTextInput(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    report_id: str | None = Field(default=None, alias="reportId", min_length=24, max_length=24)
    language: str = Field(default="en", min_length=2, max_length=12)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class AnalyzeEmailInput(BaseModel):
    subject: str | None = Field(default=None, max_length=500)
    from_: str | None = Field(default=None, alias="from", max_length=320)
    body: str = Field(min_length=1, max_length=20000)
    headers: dict[str, Any] = Field(default_factory=dict)
    forwarded_with_permission: bool = Field(default=False, alias="forwardedWithPermission")
    report_id: str | None = Field(default=None, alias="reportId", min_length=24, max_length=24)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class AnalyzeScreenshotInput(BaseModel):
    image_text: str | None = Field(default=None, alias="imageText", min_length=1, max_length=20000)
    image_base64: str | None = Field(default=None, alias="imageBase64", min_length=1)
    mime_type: str | None = Field(default=None, alias="mimeType", min_length=1, max_length=120)
    evidence_id: str | None = Field(default=None, alias="evidenceId", min_length=24, max_length=24)
    report_id: str | None = Field(default=None, alias="reportId", min_length=24, max_length=24)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def require_image_content(self) -> "AnalyzeScreenshotInput":
        if not self.image_text and not self.image_base64:
            raise ValueError("imageText or imageBase64 is required")
        return self


class CheckUrlInput(BaseModel):
    url: str
    report_id: str | None = Field(default=None, alias="reportId", min_length=24, max_length=24)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class RedactScamContentInput(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    replacement: str = "labels"

    @field_validator("replacement")
    @classmethod
    def validate_replacement(cls, value: str) -> str:
        if value not in {"mask", "labels"}:
            raise ValueError("replacement must be 'mask' or 'labels'")
        return value


class GenerateReportDraftInput(BaseModel):
    analysis_id: str | None = Field(default=None, alias="analysisId", min_length=24, max_length=24)
    analysis_snapshot: dict[str, Any] | None = Field(default=None, alias="analysisSnapshot")
    notes: str | None = Field(default=None, max_length=4000)
    auto_redact_pii: bool = Field(default=False, alias="autoRedactPII")
    redaction_mode: str = Field(default="labels", alias="redactionMode")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def require_analysis_source(self) -> "GenerateReportDraftInput":
        if not self.analysis_id and not self.analysis_snapshot:
            raise ValueError("analysisId or analysisSnapshot is required")
        return self


class GenerateReportDraftByIdInput(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    auto_redact_pii: bool = Field(default=False, alias="autoRedactPII")
    redaction_mode: str = Field(default="labels", alias="redactionMode")

    model_config = ConfigDict(populate_by_name=True)


class SubmitScamReportInput(BaseModel):
    analysis_id: str | None = Field(default=None, alias="analysisId", min_length=24, max_length=24)
    analysis_snapshot: dict[str, Any] | None = Field(default=None, alias="analysisSnapshot")
    destination: str = Field(default="SafeSpeak review queue", min_length=1, max_length=120)
    consent_to_share: bool = Field(default=False, alias="consentToShare")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def require_analysis_source(self) -> "SubmitScamReportInput":
        if not self.analysis_id and not self.analysis_snapshot:
            raise ValueError("analysisId or analysisSnapshot is required")
        return self


class SubmitScamReportByIdInput(BaseModel):
    destination: str = Field(default="SafeSpeak review queue", min_length=1, max_length=120)
    consent_to_share: bool = Field(default=False, alias="consentToShare")

    model_config = ConfigDict(populate_by_name=True)


class AnalysisSnapshot(BaseModel):
    type: str = "text"
    input_hash: str | None = Field(default=None, alias="inputHash")
    risk_level: str = Field(default="low", alias="riskLevel")
    risk_score: int = Field(default=0, alias="riskScore")
    confidence: str | None = None
    summary: str | None = None
    indicators: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list, alias="redFlags")
    recommendations: list[str] = Field(default_factory=list)
    extracted_entities: dict[str, Any] | None = Field(default=None, alias="extractedEntities")
    redacted_content: str | None = Field(default=None, alias="redactedContent")
    draft_report: dict[str, Any] | None = Field(default=None, alias="draftReport")
    status: str = "draft"
    submitted_at: str | None = Field(default=None, alias="submittedAt")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in SCAMSHIELD_ANALYSIS_TYPES:
            raise ValueError("Invalid ScamShield analysis type")
        return value

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, value: str) -> str:
        if value not in SCAMSHIELD_RISK_LEVELS:
            raise ValueError("Invalid ScamShield risk level")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in SCAMSHIELD_STATUSES:
            raise ValueError("Invalid ScamShield status")
        return value


def parse_metadata_form(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("metadata must be a JSON object")
    return parsed
