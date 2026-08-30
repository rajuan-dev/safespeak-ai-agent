from datetime import datetime
from typing import Any, Literal

from pydantic import Field, HttpUrl

from app.models.common import JURISDICTIONS, StrictModel

from .model import SourceStatus


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


class RagDebugRetrieveInput(SearchInput):
    topK: int = Field(default=5, ge=1, le=20)


class KnowledgeSourceCreate(StrictModel):
    sourceId: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    sourceTitle: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    sourceCategory: str
    jurisdiction: JURISDICTIONS
    stateOrTerritory: str | None = None
    pathwayCategory: str | None = None
    legalDomain: str | None = None
    topic: str
    legislationName: str | None = Field(default=None, max_length=200)
    sourceType: str
    sourceAuthority: str | None = Field(default=None, max_length=200)
    authority: str | None = Field(default=None, max_length=200)
    officialUrl: HttpUrl | None = None
    country: str | None = Field(default=None, max_length=80)
    language: str = Field(default="en", min_length=2, max_length=12)
    url: HttpUrl | None = None
    localFilePath: str | None = Field(default=None, max_length=1000)
    publisher: str = Field(min_length=1, max_length=200)
    licenseStatus: str = Field(min_length=1, max_length=200)
    lastUpdated: datetime | None = None
    sourceDate: datetime | None = None
    lastVerifiedAt: datetime | None = None
    nextReviewAt: datetime | None = None
    nextRefreshAt: datetime | None = None
    refreshCadence: str | None = Field(default=None, max_length=80)
    legalReviewed: bool = False
    active: bool = True
    sourceReliability: str = "unknown"
    reviewNotes: str | None = Field(default=None, max_length=2000)
    status: SourceStatus = "draft"
    version: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSourceUpdate(StrictModel):
    sourceId: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    sourceTitle: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    sourceCategory: str | None = None
    jurisdiction: JURISDICTIONS | None = None
    stateOrTerritory: str | None = None
    pathwayCategory: str | None = None
    legalDomain: str | None = None
    topic: str | None = None
    legislationName: str | None = Field(default=None, max_length=200)
    sourceType: str | None = None
    sourceAuthority: str | None = Field(default=None, max_length=200)
    authority: str | None = Field(default=None, max_length=200)
    officialUrl: HttpUrl | None = None
    country: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, min_length=2, max_length=12)
    url: HttpUrl | None = None
    localFilePath: str | None = Field(default=None, max_length=1000)
    publisher: str | None = Field(default=None, min_length=1, max_length=200)
    licenseStatus: str | None = Field(default=None, min_length=1, max_length=200)
    lastUpdated: datetime | None = None
    sourceDate: datetime | None = None
    lastVerifiedAt: datetime | None = None
    nextReviewAt: datetime | None = None
    nextRefreshAt: datetime | None = None
    refreshCadence: str | None = Field(default=None, max_length=80)
    legalReviewed: bool | None = None
    active: bool | None = None
    sourceReliability: str | None = None
    reviewNotes: str | None = Field(default=None, max_length=2000)
    status: SourceStatus | None = None
    version: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] | None = None


class KnowledgeIngestInput(StrictModel):
    content: str | None = Field(default=None, min_length=1, max_length=2_000_000)
    localFilePath: str | None = Field(default=None, min_length=1, max_length=1000)
    expectedSha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeRefreshInput(KnowledgeIngestInput):
    nextRefreshAt: datetime | None = None


class RejectInput(StrictModel):
    reason: str = Field(min_length=1, max_length=1000)


class RunKnowledgeSourceOcrInput(StrictModel):
    maxPages: int | None = Field(default=None, ge=0)
    batchSize: int | None = Field(default=None, ge=1)
    pageTimeoutMs: int | None = Field(default=None, ge=1)
    jobTimeoutMs: int | None = Field(default=None, ge=0)
    force: bool = False


class ApproveOcrKnowledgeSourceInput(StrictModel):
    legalReviewed: bool = True


class KnowledgeSourceChunkQueryInput(StrictModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=25, ge=1, le=50)


class KnowledgeSourceOcrPreviewQueryInput(StrictModel):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=5, ge=1, le=20)
