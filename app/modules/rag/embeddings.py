from typing import Any

from app.services.embeddings import embedding_service
from app.services.vector_store import pinecone_store


async def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    return await embedding_service.embed(texts, model=model)


async def pinecone_health() -> dict[str, Any]:
    return await pinecone_store.health()


__all__ = ["embed_texts", "pinecone_health", "pinecone_store"]
