from pydantic import BaseModel


class TaxonomyQueryInput(BaseModel):
    type: str | None = None
    isActive: bool | None = None


class TaxonomyInput(BaseModel):
    type: str
    key: str
    label: str
    description: str | None = None
    isActive: bool = True
    metadata: dict | None = None


class UpdateTaxonomyInput(BaseModel):
    type: str | None = None
    key: str | None = None
    label: str | None = None
    description: str | None = None
    isActive: bool | None = None
    metadata: dict | None = None
