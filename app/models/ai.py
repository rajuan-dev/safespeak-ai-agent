from typing import Any, Literal

from pydantic import Field

from app.models.common import StrictModel

OBJECT_ID_PATTERN = r"^[0-9a-fA-F]{24}$"
LanguageCode = Field(default=None, min_length=2, max_length=12)
IncidentCategory = Literal[
    "domestic_violence",
    "racial_abuse",
    "migrant_challenges",
    "cyber_scam",
]


class BaseAiInput(StrictModel):
    reportId: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    language: str | None = LanguageCode
    incidentCategory: IncidentCategory | None = None


class ExtractIncidentFieldsInput(BaseAiInput):
    narrative: str = Field(min_length=1, max_length=12_000)
    jurisdiction: str | None = None


class ClarifyingQuestionsInput(BaseAiInput):
    narrative: str = Field(min_length=1, max_length=12_000)
    structuredFields: dict[str, Any] | None = None
    maxQuestions: int = Field(default=12, ge=1, le=25)


class GenerateSummaryInput(BaseAiInput):
    narrative: str | None = Field(default=None, max_length=12_000)
    structuredFields: dict[str, Any] | None = None
    audience: Literal["user", "support_worker", "reviewer"] = "user"


class TriageInput(BaseAiInput):
    narrative: str | None = Field(default=None, max_length=12_000)
    structuredFields: dict[str, Any] | None = None


class TranslateInput(StrictModel):
    text: str = Field(min_length=1, max_length=12_000)
    sourceLanguage: str | None = None
    targetLanguage: str = Field(default="English", min_length=2, max_length=40)


class RedactInput(StrictModel):
    text: str = Field(min_length=1, max_length=12_000)
    language: str | None = LanguageCode
    replacementStyle: Literal["labels", "mask"] = "labels"


class TranscribeAudioInput(StrictModel):
    reportId: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    evidenceId: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    language: str | None = Field(default=None, min_length=2, max_length=40)
    saveTranscript: bool | None = None
    useAsNarrative: bool | None = None


class SynthesizeSpeechInput(StrictModel):
    text: str = Field(min_length=1, max_length=4_000)
    language: str | None = LanguageCode
    voice: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,40}$")
