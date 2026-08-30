from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

DEFAULT_SESSION_LANGUAGE = "en"
DEFAULT_SESSION_JURISDICTION = "NSW"
ANONYMOUS_SESSION_TTL_DAYS = 30
SAFE_SPEAK_SESSION_HEADER = "X-SafeSpeak-Session"


class AnonymousSessionDocument(BaseModel):
    session_token_hash: str = Field(alias="sessionTokenHash")
    user_id: str | None = Field(default=None, alias="userId")
    is_anonymous: bool = Field(default=True, alias="isAnonymous")
    safety_gate_accepted_at: datetime | None = Field(
        default=None, alias="safetyGateAcceptedAt"
    )
    language: str = DEFAULT_SESSION_LANGUAGE
    jurisdiction: str = DEFAULT_SESSION_JURISDICTION
    lga: str | None = None
    consent_snapshot: dict[str, object] = Field(default_factory=dict, alias="consentSnapshot")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC) + timedelta(days=ANONYMOUS_SESSION_TTL_DAYS),
        alias="expiresAt",
    )

    model_config = {"populate_by_name": True}
