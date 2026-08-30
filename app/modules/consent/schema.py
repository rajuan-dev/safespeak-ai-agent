from pydantic import BaseModel, ConfigDict, Field, field_validator

from .model import CONSENT_FLAGS


class UpdateConsentInput(BaseModel):
    flags: dict[str, bool]
    source: str = Field(default="user", min_length=1, max_length=80)

    model_config = ConfigDict(extra="forbid")

    @field_validator("flags")
    @classmethod
    def validate_flags(cls, value: dict[str, bool]) -> dict[str, bool]:
        invalid = [key for key in value if key not in CONSENT_FLAGS]
        if invalid:
            raise ValueError(f"Unsupported consent flags: {', '.join(invalid)}")
        return value


class WithdrawConsentInput(BaseModel):
    flags: list[str]
    source: str = Field(default="withdrawal", min_length=1, max_length=80)

    model_config = ConfigDict(extra="forbid")

    @field_validator("flags")
    @classmethod
    def validate_flags(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("List should have at least 1 item after validation, not 0")
        invalid = [flag for flag in value if flag not in CONSENT_FLAGS]
        if invalid:
            raise ValueError(f"Unsupported consent flags: {', '.join(invalid)}")
        return value
