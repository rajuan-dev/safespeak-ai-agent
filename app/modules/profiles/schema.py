from pydantic import BaseModel, ConfigDict, Field


class UpdateProfileInput(BaseModel):
    preferred_language: str | None = Field(
        default=None, alias="preferredLanguage", min_length=2, max_length=12
    )
    interpreter_language: str | None = Field(
        default=None, alias="interpreterLanguage", min_length=2, max_length=80
    )
    jurisdiction: str | None = Field(default=None, min_length=2, max_length=80)
    lga: str | None = Field(default=None, max_length=120)
    cultural_profile: str | None = Field(default=None, alias="culturalProfile", max_length=120)
    faith_profile: str | None = Field(default=None, alias="faithProfile", max_length=120)
    community_profile: str | None = Field(default=None, alias="communityProfile", max_length=120)
    referral_sharing_preference: bool | None = Field(
        default=None, alias="referralSharingPreference"
    )
    accessibility_preferences: dict[str, object] | None = Field(
        default=None, alias="accessibilityPreferences"
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
