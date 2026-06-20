from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "SafeSpeak AI Agent"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    MONGODB_URI: str
    MONGODB_DATABASE: str | None = None
    JWT_ACCESS_SECRET: str = Field(min_length=32)

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-5.2"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"

    PINECONE_API_KEY: str | None = None
    PINECONE_INDEX_NAME: str = "safespeak-legislation-dev"
    PINECONE_NAMESPACE: str = "dev"

    RAG_TOP_K_LEGAL: int = 6
    RAG_MIN_SCORE_LEGAL: float = 0.55
    RAG_MAX_CHUNKS_PER_SOURCE: int = 3
    RAG_RERANK_PROVIDER: str = "hybrid"
    RAG_RERANK_CANDIDATES: int = 20
    RAG_REQUIRE_COMPLETE_CITATIONS: bool = True
    RAG_MIN_CLAIM_SUPPORT_SCORE: float = 0.18
    RAG_CHUNK_TARGET_CHARS: int = 2400
    RAG_CHUNK_MAX_CHARS: int = 3600
    RAG_ENABLE_OCR: bool = False
    OCR_LANGUAGE: str = "eng"
    OCR_MIN_CONFIDENCE: float = 0.85
    OCR_REVIEW_REQUIRED: bool = True
    TESSERACT_CMD: Path | None = None
    TESSDATA_PATH: Path = Path("./tools/tessdata")
    LEGAL_REQUIRE_PRODUCTION_GOLDEN: bool = True
    LEGAL_FAIL_CLOSED_ON_STARTUP: bool = True
    LEGAL_GOLDEN_REPORT_PATH: Path = Path("./legal-golden/reports/latest.json")
    KNOWLEDGE_STORAGE_PATH: Path = Path("./storage/knowledge-sources")
    MAX_UPLOAD_BYTES: int = 52_428_800

    BACKEND_API_BASE_URL: str = "http://localhost:5000/api/v1"

    @field_validator("API_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        return "/" + value.strip("/")

    @field_validator("TESSERACT_CMD", mode="before")
    @classmethod
    def empty_tesseract_path_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.CORS_ALLOWED_ORIGINS.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
