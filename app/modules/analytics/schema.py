from pydantic import BaseModel, Field


class AnalyticsQueryInput(BaseModel):
    from_date: str | None = Field(default=None, alias="from")
    to_date: str | None = Field(default=None, alias="to")
    jurisdiction: str | None = None
    language: str | None = None

    model_config = {"populate_by_name": True}


class AnalyticsExportQueryInput(AnalyticsQueryInput):
    format: str = "json"

