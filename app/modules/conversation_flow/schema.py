from pydantic import BaseModel, ConfigDict, Field

from .model import CONVERSATION_FLOW_STATUSES


class CreateConversationFlowSessionInput(BaseModel):
    selected_topic: str | None = Field(default=None, alias="selectedTopic", max_length=120)
    jurisdiction: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)

    model_config = ConfigDict(populate_by_name=True)


class AppendConversationFlowMessageInput(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=12)
    debug_response: str | None = Field(default=None, alias="debugResponse")

    model_config = ConfigDict(populate_by_name=True)


class ConversationTransition(BaseModel):
    offer_triage: bool = Field(alias="offerTriage")
    prompt: str | None = None
    primary_cta: str | None = Field(default=None, alias="primaryCta")
    secondary_cta: str | None = Field(default=None, alias="secondaryCta")

    model_config = ConfigDict(populate_by_name=True)


class ConversationSessionRecord(BaseModel):
    id: str
    selected_topic: str | None = Field(default=None, alias="selectedTopic")
    detected_category: str | None = Field(default=None, alias="detectedCategory")
    detected_language: str | None = Field(default=None, alias="detectedLanguage")
    status: str = Field(default=CONVERSATION_FLOW_STATUSES[0])
    safety_risk_level: str = Field(alias="safetyRiskLevel")
    active_issue_id: str | None = Field(default=None, alias="activeIssueId")
    latest_turn_risk_level: str | None = Field(default=None, alias="latestTurnRiskLevel")
    active_incident_risk_level: str | None = Field(
        default=None, alias="activeIncidentRiskLevel"
    )
    session_historical_max_risk_level: str | None = Field(
        default=None, alias="sessionHistoricalMaxRiskLevel"
    )
    assistant_format_preference: str | None = Field(
        default=None, alias="assistantFormatPreference"
    )
    jurisdiction: str | None = None
    location: str | None = None
    message_count: int = Field(alias="messageCount")
    user_turn_count: int = Field(alias="userTurnCount")
    triage_offered_at: str | None = Field(default=None, alias="triageOfferedAt")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
