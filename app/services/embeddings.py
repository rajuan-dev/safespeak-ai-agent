from openai import AsyncOpenAI

from app.core.config import get_settings


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 64):
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts[start : start + 64],
            )
            vectors.extend(item.embedding for item in response.data)
        return vectors


embedding_service = EmbeddingService()
