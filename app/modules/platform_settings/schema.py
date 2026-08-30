from pydantic import BaseModel


class SafetySettingsInput(BaseModel):
    immediateDangerText: str | None = None
    respectSupportText: str | None = None
    platformRoleText: str | None = None
    informationOnlyText: str | None = None
    emergencyCallLabel: str | None = None
    respectCallLabel: str | None = None
    quickExitLabel: str | None = None
    covertModeLabel: str | None = None


class ConsentSettingsInput(BaseModel):
    introText: str | None = None
    localStorageLabel: str | None = None
    cloudSyncLabel: str | None = None
    agencySharingLabel: str | None = None
    analyticsLabel: str | None = None


class AISettingsInput(BaseModel):
    disclaimerText: str | None = None
    humanReviewText: str | None = None
    triageSystemPrompt: str | None = None
    triageResponseTemplate: str | None = None
    triageFallbackText: str | None = None
    triageTemplateStatus: str | None = None


class PlatformSettingsInput(BaseModel):
    safety: SafetySettingsInput | None = None
    consent: ConsentSettingsInput | None = None
    ai: AISettingsInput | None = None
