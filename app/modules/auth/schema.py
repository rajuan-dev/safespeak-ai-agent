from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise ValueError("value is not a valid email address")
    return normalized


class RegisterInput(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=128)
    full_name: str | None = Field(default=None, alias="fullName", min_length=1, max_length=120)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _ensure_email(value)


class LoginInput(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _ensure_email(value)


class RefreshTokenInput(BaseModel):
    refresh_token: str = Field(alias="refreshToken", min_length=20)

    model_config = ConfigDict(populate_by_name=True)


class ChangePasswordInput(BaseModel):
    current_password: str = Field(alias="currentPassword", min_length=1, max_length=128)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=128)

    model_config = ConfigDict(populate_by_name=True)


class UpdateCurrentUserProfileInput(BaseModel):
    full_name: str | None = Field(default=None, alias="fullName", min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    contact_no: str | None = Field(default=None, alias="contactNo", max_length=80)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        return _ensure_email(value) if value is not None else value


class ForgotPasswordInput(BaseModel):
    email: str
    audience: str = "admin"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _ensure_email(value)

    @field_validator("audience")
    @classmethod
    def validate_audience(cls, value: str) -> str:
        if value not in {"admin", "public"}:
            raise ValueError("Input should be 'admin' or 'public'")
        return value


class VerifyPasswordResetOtpInput(BaseModel):
    email: str
    audience: str = "admin"
    reset_request_id: str = Field(alias="resetRequestId", pattern=r"^[0-9a-fA-F]{24}$")
    otp: str = Field(pattern=r"^\d{4}$")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _ensure_email(value)

    @field_validator("audience")
    @classmethod
    def validate_audience(cls, value: str) -> str:
        if value not in {"admin", "public"}:
            raise ValueError("Input should be 'admin' or 'public'")
        return value


class ResetPasswordInput(BaseModel):
    email: str
    audience: str = "admin"
    reset_request_id: str = Field(alias="resetRequestId", pattern=r"^[0-9a-fA-F]{24}$")
    reset_token: str = Field(alias="resetToken", min_length=32, max_length=256)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=128)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _ensure_email(value)

    @field_validator("audience")
    @classmethod
    def validate_audience(cls, value: str) -> str:
        if value not in {"admin", "public"}:
            raise ValueError("Input should be 'admin' or 'public'")
        return value


class DeactivateAccountInput(BaseModel):
    confirmation: str

    @field_validator("confirmation")
    @classmethod
    def validate_confirmation(cls, value: str) -> str:
        if value != "DEACTIVATE":
            raise ValueError("Input should be 'DEACTIVATE'")
        return value
