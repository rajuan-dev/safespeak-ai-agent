from pydantic import Field

from app.models.common import StrictModel


class InternalCompletionInput(StrictModel):
    systemPrompt: str = Field(min_length=1, max_length=100_000)
    userPrompt: str = Field(min_length=1, max_length=200_000)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    temperature: float = Field(default=0.2, ge=0, le=2)


class InternalEmbeddingInput(StrictModel):
    texts: list[str] = Field(min_length=1, max_length=256)
    model: str | None = Field(default=None, min_length=1, max_length=120)


class InternalVisionInput(StrictModel):
    instruction: str = Field(min_length=1, max_length=10_000)
    imageData: str = Field(min_length=1, max_length=20_000_000)
    model: str | None = Field(default=None, min_length=1, max_length=120)
