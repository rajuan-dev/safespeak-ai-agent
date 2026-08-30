from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PROFILE_LANGUAGE = "en"
DEFAULT_PROFILE_JURISDICTION = "NSW"


class UserProfileDocument(BaseModel):
    user_id: str | None = Field(default=None, alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    preferred_language: str = Field(default=DEFAULT_PROFILE_LANGUAGE, alias="preferredLanguage")
    interpreter_language: str | None = Field(default=None, alias="interpreterLanguage")
    jurisdiction: str = DEFAULT_PROFILE_JURISDICTION
    lga: str | None = None
    cultural_profile: str | None = Field(default=None, alias="culturalProfile")
    faith_profile: str | None = Field(default=None, alias="faithProfile")
    community_profile: str | None = Field(default=None, alias="communityProfile")
    referral_sharing_preference: bool = Field(
        default=False, alias="referralSharingPreference"
    )
    accessibility_preferences: dict[str, object] = Field(
        default_factory=dict, alias="accessibilityPreferences"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
