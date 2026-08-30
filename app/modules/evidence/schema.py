from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateEvidenceUploadUrlInput(BaseModel):
    report_id: str = Field(alias="reportId", pattern=r"^[0-9a-fA-F]{24}$")
    type: str = Field(min_length=1, max_length=80)
    file_name: str = Field(alias="fileName", min_length=1, max_length=255)
    mime_type: str = Field(alias="mimeType", min_length=1, max_length=120)
    size: int = Field(gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class VerifyHashInput(BaseModel):
    sha256_hash: str = Field(alias="sha256Hash", pattern=r"^[a-fA-F0-9]{64}$")

    model_config = ConfigDict(populate_by_name=True)


class TranscribeEvidenceInput(BaseModel):
    language: str | None = None
    save_transcript: bool = Field(default=True, alias="saveTranscript")
    report_id: str | None = Field(default=None, alias="reportId")
    use_as_narrative: bool = Field(default=False, alias="useAsNarrative")

    model_config = ConfigDict(populate_by_name=True)


class CompleteEvidenceUploadFormInput(BaseModel):
    evidence_id: str = Field(alias="evidenceId", pattern=r"^[0-9a-fA-F]{24}$")
    sha256_hash: str = Field(alias="sha256Hash", pattern=r"^[a-fA-F0-9]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("metadata", mode="before")
    @classmethod
    def decode_metadata(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, str):
            import json

            return json.loads(value)
        return value
