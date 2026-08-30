from pydantic import BaseModel, Field

from app.modules.sessions.model import (
    DEFAULT_SESSION_JURISDICTION,
    DEFAULT_SESSION_LANGUAGE,
)


class CreateAnonymousSessionInput(BaseModel):
    language: str | None = Field(default=DEFAULT_SESSION_LANGUAGE, min_length=2, max_length=12)
    jurisdiction: str | None = Field(
        default=DEFAULT_SESSION_JURISDICTION, min_length=2, max_length=80
    )
    lga: str | None = Field(default=None, max_length=120)
    safety_gate_accepted: bool | None = Field(default=False, alias="safetyGateAccepted")

    model_config = {"populate_by_name": True}


class ConvertToUserInput(BaseModel):
    user_id: str = Field(alias="userId", pattern=r"^[a-f\d]{24}$")

    model_config = {"populate_by_name": True}


class AuthenticatedSession(BaseModel):
    id: str
    user_id: str | None = Field(default=None, alias="userId")
    is_anonymous: bool = Field(alias="isAnonymous")
    language: str
    jurisdiction: str
    lga: str | None = None

    model_config = {"populate_by_name": True}
