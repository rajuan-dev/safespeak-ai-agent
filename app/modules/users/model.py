from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(populate_by_name=True)


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

    model_config = ConfigDict(populate_by_name=True)
