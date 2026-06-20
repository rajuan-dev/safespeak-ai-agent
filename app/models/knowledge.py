from datetime import datetime
from typing import Any, Literal

from pydantic import Field, HttpUrl

from app.models.common import JURISDICTIONS, StrictModel

SOURCE_STATUSES = Literal["draft", "pending_review", "approved", "rejected", "expired", "archived"]


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
    officialUrl: HttpUrl | None = None
    country: str | None = Field(default=None, max_length=80)
    language: str = Field(default="en", min_length=2, max_length=12)
    url: HttpUrl | None = None
    localFilePath: str | None = Field(default=None, max_length=1000)
    publisher: str = Field(min_length=1, max_length=200)
    licenseStatus: str = Field(min_length=1, max_length=200)
    lastUpdated: datetime | None = None
    lastVerifiedAt: datetime | None = None
    nextReviewAt: datetime | None = None
    nextRefreshAt: datetime | None = None
    legalReviewed: bool = False
    active: bool = True
    sourceReliability: str = "unknown"
    reviewNotes: str | None = Field(default=None, max_length=2000)
    status: SOURCE_STATUSES = "draft"
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
    officialUrl: HttpUrl | None = None
    country: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, min_length=2, max_length=12)
    url: HttpUrl | None = None
    localFilePath: str | None = Field(default=None, max_length=1000)
    publisher: str | None = Field(default=None, min_length=1, max_length=200)
    licenseStatus: str | None = Field(default=None, min_length=1, max_length=200)
    lastUpdated: datetime | None = None
    lastVerifiedAt: datetime | None = None
    nextReviewAt: datetime | None = None
    nextRefreshAt: datetime | None = None
    legalReviewed: bool | None = None
    active: bool | None = None
    sourceReliability: str | None = None
    reviewNotes: str | None = Field(default=None, max_length=2000)
    status: SOURCE_STATUSES | None = None
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
