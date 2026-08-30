from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

CONSENT_FLAGS = (
    "store_local",
    "cloud_sync",
    "share_with_agencies",
    "use_anonymised_analytics",
    "process_with_ai",
    "transcribe_audio",
    "translate_content",
    "retain_evidence",
    "warm_referral",
    "advocate_request",
)

DEFAULT_CONSENT_FLAGS = {
    "store_local": True,
    "cloud_sync": False,
    "share_with_agencies": False,
    "use_anonymised_analytics": False,
    "process_with_ai": False,
    "transcribe_audio": False,
    "translate_content": False,
    "retain_evidence": False,
    "warm_referral": False,
    "advocate_request": False,
}


class ConsentRecordDocument(BaseModel):
    user_id: str | None = Field(default=None, alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    flags: dict[str, bool] = Field(default_factory=lambda: dict(DEFAULT_CONSENT_FLAGS))
    version: int
    source: str
    ip_hash: str | None = Field(default=None, alias="ipHash")
    user_agent_hash: str | None = Field(default=None, alias="userAgentHash")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)
