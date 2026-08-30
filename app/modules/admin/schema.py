from pydantic import BaseModel


class UsersQueryInput(BaseModel):
    role: str | None = None
    status: str | None = None
    search: str | None = None
    limit: int = 50


class CreateAdminUserInput(BaseModel):
    email: str
    fullName: str
    password: str
    role: str
    status: str = "active"


class UpdateAdminUserInput(BaseModel):
    fullName: str | None = None
    role: str | None = None
    status: str | None = None


class DestinationsQueryInput(BaseModel):
    type: str | None = None
    channel: str | None = None
    jurisdiction: str | None = None
    isActive: bool | None = None


class DestinationInput(BaseModel):
    type: str
    key: str
    name: str
    channel: str
    jurisdiction: str
    languages: list[str] = []
    endpoint: str | None = None
    contactEmail: str | None = None
    contactPhone: str | None = None
    minimumRequiredInfo: list[str] = []
    anonymityOptions: list[str] = []
    expectedNextSteps: list[str] = []
    consentRequired: bool = True
    supportsAcknowledgement: bool = False
    isActive: bool = True
    metadata: dict | None = None


class UpdateDestinationInput(BaseModel):
    type: str | None = None
    key: str | None = None
    name: str | None = None
    channel: str | None = None
    jurisdiction: str | None = None
    languages: list[str] | None = None
    endpoint: str | None = None
    contactEmail: str | None = None
    contactPhone: str | None = None
    minimumRequiredInfo: list[str] | None = None
    anonymityOptions: list[str] | None = None
    expectedNextSteps: list[str] | None = None
    consentRequired: bool | None = None
    supportsAcknowledgement: bool | None = None
    isActive: bool | None = None
    metadata: dict | None = None


class SubmissionTemplatesQueryInput(BaseModel):
    destinationType: str | None = None
    channel: str | None = None
    jurisdiction: str | None = None
    isActive: bool | None = None


class SubmissionTemplateInput(BaseModel):
    key: str
    name: str
    destinationType: str
    channel: str
    jurisdiction: str
    titleTemplate: str
    summaryTemplate: str
    fieldMappings: list[dict] = []
    staticPayload: dict | None = None
    acknowledgementMode: str
    attachmentMode: str
    isActive: bool = True
    metadata: dict | None = None


class UpdateSubmissionTemplateInput(BaseModel):
    key: str | None = None
    name: str | None = None
    destinationType: str | None = None
    channel: str | None = None
    jurisdiction: str | None = None
    titleTemplate: str | None = None
    summaryTemplate: str | None = None
    fieldMappings: list[dict] | None = None
    staticPayload: dict | None = None
    acknowledgementMode: str | None = None
    attachmentMode: str | None = None
    isActive: bool | None = None
    metadata: dict | None = None


class ReportDeliveriesQueryInput(BaseModel):
    status: str | None = None
    destinationType: str | None = None
    channel: str | None = None
    limit: int = 50


class PrivacyRequestsQueryInput(BaseModel):
    status: str | None = None
    limit: int = 50


class UpdatePrivacyRequestInput(BaseModel):
    status: str
    notes: str | None = None


class NotificationsQueryInput(BaseModel):
    limit: int = 25


class NotificationReadInput(BaseModel):
    notificationId: str


class NotificationReadAllInput(BaseModel):
    before: str | None = None


class SupportServicesQueryInput(BaseModel):
    type: str | None = None
    resourceType: str | None = None
    issueType: str | None = None
    jurisdiction: str | None = None
    language: str | None = None
    region: str | None = None
    eligibility: str | None = None
    profile: str | None = None
    isPublished: bool | None = None
    isActive: bool | None = None


class SupportServiceInput(BaseModel):
    key: str
    name: str
    type: str
    description: str
    resourceType: str
    issueTypes: list[str] = []
    safetyRiskLevels: list[str] = []
    ctaLabel: str
    resourceLinks: list[dict] = []
    jurisdiction: str
    regions: list[str] = []
    languages: list[str] = []
    eligibility: list[str] = []
    crisis: bool = False
    informationOnly: bool = True
    isPublished: bool = True
    isActive: bool = True
    sortOrder: int = 0
    metadata: dict | None = None


class UpdateSupportServiceInput(BaseModel):
    key: str | None = None
    name: str | None = None
    type: str | None = None
    description: str | None = None
    resourceType: str | None = None
    issueTypes: list[str] | None = None
    safetyRiskLevels: list[str] | None = None
    ctaLabel: str | None = None
    resourceLinks: list[dict] | None = None
    jurisdiction: str | None = None
    regions: list[str] | None = None
    languages: list[str] | None = None
    eligibility: list[str] | None = None
    crisis: bool | None = None
    informationOnly: bool | None = None
    isPublished: bool | None = None
    isActive: bool | None = None
    sortOrder: int | None = None
    metadata: dict | None = None


class WarmReferralsQueryInput(BaseModel):
    status: str | None = None
    serviceId: str | None = None
    limit: int = 50


class UpdateWarmReferralInput(BaseModel):
    status: str
    notes: str | None = None
