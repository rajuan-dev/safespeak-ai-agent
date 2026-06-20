from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JURISDICTIONS = Literal[
    "Cth", "NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT", "AU", "Global", "Internal"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class SearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    topK: int = Field(default=5, ge=1, le=20)
    language: str | None = Field(default=None, min_length=2, max_length=12)
    jurisdiction: JURISDICTIONS | None = None
    sourceIds: list[str] | None = Field(default=None, max_length=20)
    stateOrTerritory: str | None = None
    legalDomain: str | None = None
    pathwayCategory: str | None = None
    sourceCategory: str | None = None
    topic: str | None = None
    filters: dict[str, Any] | None = None


class AnswerInput(SearchInput):
    question: str = Field(min_length=1, max_length=2000)


class ConversationMessage(StrictModel):
    role: Literal["assistant", "user"]
    content: str = Field(min_length=1, max_length=4000)


class TimelineAssistantInput(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=100)
    timeline: dict[str, Any] = Field(default_factory=dict)
    language: str | None = None
    incidentCategory: str | None = None
    jurisdiction: JURISDICTIONS | None = None
    topK: int = Field(default=4, ge=1, le=8)

