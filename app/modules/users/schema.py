from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise ValueError("value is not a valid email address")
    return normalized


class UpdateUserInput(BaseModel):
    full_name: str | None = Field(default=None, alias="fullName", min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    contact_no: str | None = Field(default=None, alias="contactNo", max_length=80)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return _ensure_email(value) if value is not None else value
