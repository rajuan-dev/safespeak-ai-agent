from pydantic import BaseModel, ConfigDict, Field, field_validator

from .model import PRIVACY_REQUEST_TYPES


class CreatePrivacyRequestInput(BaseModel):
    request_type: str = Field(alias="requestType")
    notes: str | None = Field(default=None, max_length=2000)
    confirmation: bool = False

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, value: str) -> str:
        if value not in PRIVACY_REQUEST_TYPES:
            raise ValueError("Input should be a valid privacy request type")
        return value


class DeleteRequestInput(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    confirmation: bool = False

    model_config = ConfigDict(extra="forbid")


class PrivacyRequestParams(BaseModel):
    id: str = Field(pattern=r"^[0-9a-fA-F]{24}$")
