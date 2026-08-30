from pydantic import BaseModel


class ResourceQueryInput(BaseModel):
    status: str | None = None
    search: str | None = None


class ResourceInput(BaseModel):
    name: str
    category: str
    region: str | None = None
    contact: dict | None = None
    status: str = "published"
    sortOrder: int = 0


class UpdateResourceInput(BaseModel):
    name: str | None = None
    category: str | None = None
    region: str | None = None
    contact: dict | None = None
    status: str | None = None
    sortOrder: int | None = None
