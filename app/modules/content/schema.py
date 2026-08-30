from pydantic import BaseModel


class ContentResourceInput(BaseModel):
    name: str
    language: str
    category: str
    jurisdiction: str
    reviewDate: str | None = None
    status: str = "draft"


class ContentResourceUpdateInput(BaseModel):
    name: str | None = None
    language: str | None = None
    category: str | None = None
    jurisdiction: str | None = None
    reviewDate: str | None = None
    status: str | None = None


class MicroEducationCategoryInput(BaseModel):
    name: str
    description: str | None = None
    backgroundColor: str
    textColor: str
    iconName: str | None = None
    imageUrl: str | None = None
    status: str = "draft"
    sortOrder: int = 0


class MicroEducationCategoryUpdateInput(BaseModel):
    name: str | None = None
    description: str | None = None
    backgroundColor: str | None = None
    textColor: str | None = None
    iconName: str | None = None
    imageUrl: str | None = None
    status: str | None = None
    sortOrder: int | None = None


class GenerateMicroEducationInput(BaseModel):
    topic: str
    audience: str | None = None
    language: str | None = None
    tone: str | None = None
    categoryId: str | None = None


class MicroEducationInput(BaseModel):
    title: str
    summary: str
    readTimeLabel: str
    tag: str
    cta: str
    detailHeading: str
    detailSummary: str | None = None
    detailBody: str
    detailTakeaway: str
    imageAlt: str | None = None
    categoryId: str | None = None
    tone: str
    chips: list[str] = []
    incidentCategories: list[str] | None = None
    matchKeywords: list[str] | None = None
    duration: str
    format: str
    status: str = "draft"
    sortOrder: int = 0
    views: int = 0


class MicroEducationUpdateInput(BaseModel):
    title: str | None = None
    summary: str | None = None
    readTimeLabel: str | None = None
    tag: str | None = None
    cta: str | None = None
    detailHeading: str | None = None
    detailSummary: str | None = None
    detailBody: str | None = None
    detailTakeaway: str | None = None
    imageAlt: str | None = None
    categoryId: str | None = None
    tone: str | None = None
    chips: list[str] | None = None
    incidentCategories: list[str] | None = None
    matchKeywords: list[str] | None = None
    duration: str | None = None
    format: str | None = None
    status: str | None = None
    sortOrder: int | None = None
    views: int | None = None
