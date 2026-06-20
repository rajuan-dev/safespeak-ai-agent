from typing import Any, Literal

from pydantic import Field

from app.models.common import StrictModel


class NarrativeInput(StrictModel):
    reportId: str | None = None
    language: str | None = None
    incidentCategory: str | None = None
    narrative: str = Field(min_length=1, max_length=20_000)
    jurisdiction: str | None = None
    structuredFields: dict[str, Any] | None = None
    maxQuestions: int | None = Field(default=None, ge=1, le=10)
    audience: Literal["user", "support_worker", "reviewer"] | None = None


class TriageInput(StrictModel):
    reportId: str | None = None
    language: str | None = None
    incidentCategory: str | None = None
    narrative: str | None = Field(default=None, max_length=20_000)
    structuredFields: dict[str, Any] | None = None


class TranslateInput(StrictModel):
    text: str = Field(min_length=1, max_length=20_000)
    sourceLanguage: str | None = None
    targetLanguage: str = Field(default="en", min_length=2, max_length=40)


class RedactInput(StrictModel):
    text: str = Field(min_length=1, max_length=20_000)
    language: str | None = None
    replacementStyle: Literal["labels", "mask"] = "labels"
