from datetime import UTC, datetime

from pydantic import BaseModel, Field


class UserDocument(BaseModel):
    email: str
    password_hash: str = Field(alias="passwordHash")
    full_name: str = Field(alias="fullName")
    contact_no: str | None = Field(default=None, alias="contactNo")
    google_id: str | None = Field(default=None, alias="googleId")
    auth_provider: str = Field(default="local", alias="authProvider")
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    role: str = "public_user"
    status: str = "active"
    is_email_verified: bool = Field(default=False, alias="isEmailVerified")
    last_login_at: datetime | None = Field(default=None, alias="lastLoginAt")
    refresh_token_hash: str | None = Field(default=None, alias="refreshTokenHash")
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")

    model_config = {"populate_by_name": True}


class PasswordResetRequestDocument(BaseModel):
    user_id: str = Field(alias="userId")
    email: str
    audience: str
    otp_hash: str = Field(alias="otpHash")
    otp_nonce: str = Field(alias="otpNonce")
    otp_attempts: int = Field(default=0, alias="otpAttempts")
    max_otp_attempts: int = Field(default=5, alias="maxOtpAttempts")
    reset_token_hash: str | None = Field(default=None, alias="resetTokenHash")
    reset_token_nonce: str | None = Field(default=None, alias="resetTokenNonce")
    reset_token_expires_at: datetime | None = Field(default=None, alias="resetTokenExpiresAt")
    verified_at: datetime | None = Field(default=None, alias="verifiedAt")
    used_at: datetime | None = Field(default=None, alias="usedAt")
    expires_at: datetime = Field(alias="expiresAt")
    delivered_at: datetime | None = Field(default=None, alias="deliveredAt")
    delivery_mode: str | None = Field(default=None, alias="deliveryMode")
    delivery_reference: str | None = Field(default=None, alias="deliveryReference")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")

    model_config = {"populate_by_name": True}


class SafeUser(BaseModel):
    id: str
    email: str
    full_name: str = Field(alias="fullName")
    contact_no: str | None = Field(default=None, alias="contactNo")
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    role: str
    status: str
    is_email_verified: bool = Field(alias="isEmailVerified")
    last_login_at: datetime | None = Field(default=None, alias="lastLoginAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class AuthTokens(BaseModel):
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")

    model_config = {"populate_by_name": True}


class AuthData(BaseModel):
    user: SafeUser
    tokens: AuthTokens


class AuthenticatedUserPayload(BaseModel):
    user_id: str = Field(alias="userId")
    role: str

    model_config = {"populate_by_name": True}
