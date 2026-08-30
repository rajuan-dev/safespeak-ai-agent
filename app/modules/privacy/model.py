from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

PRIVACY_REQUEST_TYPES = ("data_export", "data_deletion", "account_deactivation")
PRIVACY_REQUEST_STATUSES = ("pending", "in_review", "completed", "rejected")


class PrivacyRequestDocument(BaseModel):
    user_id: str | None = Field(default=None, alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    request_type: str = Field(alias="requestType")
    status: str = "pending"
    notes: str | None = None
    reviewed_by: str | None = Field(default=None, alias="reviewedBy")
    reviewed_at: datetime | None = Field(default=None, alias="reviewedAt")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
