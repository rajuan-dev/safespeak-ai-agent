from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
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
    CLIENT_URL: str = "http://localhost:3000"
    ADMIN_URL: str = "http://localhost:5173"
    NODE_ENV: str | None = None
    MONGODB_DNS_SERVERS: str | None = None
    DEBUG_FULL_RESPONSE: bool = False
    RATE_LIMIT_WINDOW_MS: int = 900000
    RATE_LIMIT_MAX: int = 100

    MONGODB_URI: str
    MONGODB_DATABASE: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MONGODB_DATABASE", "DATABASE_NAME"),
    )
    JWT_ACCESS_SECRET: str = Field(min_length=32)
    JWT_REFRESH_SECRET: str = Field(min_length=32)
    JWT_ACCESS_EXPIRES_IN: str = "15m"
    JWT_REFRESH_EXPIRES_IN: str = "7d"
    BCRYPT_SALT_ROUNDS: int = 12

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-5.2"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    OPENAI_TRANSCRIPTION_MODEL: str = "gpt-4o-transcribe"
    OPENAI_TTS_MODEL: str = "gpt-4o-mini-tts"
    OPENAI_TTS_VOICE: str = "alloy"
    ASR_MAX_FILE_SIZE_BYTES: int = 26_214_400
    AI_RESPONSE_MODE: str = "safespeak_model"

    PINECONE_API_KEY: str | None = None
    PINECONE_INDEX_NAME: str = "safespeak-legislation-dev"
    PINECONE_NAMESPACE: str = "dev"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"

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
    OCR_PROVIDER: str = "tesseract"
    OCR_LANGUAGE: str = "eng"
    OCR_MIN_CONFIDENCE: float = 0.85
    OCR_MAX_PAGES: int = 100
    OCR_BATCH_SIZE: int = 5
    OCR_PAGE_TIMEOUT_MS: int = 60000
    OCR_JOB_TIMEOUT_MS: int = 0
    OCR_REVIEW_REQUIRED: bool = True
    TESSERACT_CMD: Path | None = None
    TESSDATA_PATH: Path = Path("./tools/tessdata")
    LEGAL_REQUIRE_PRODUCTION_GOLDEN: bool = True
    LEGAL_FAIL_CLOSED_ON_STARTUP: bool = True
    LEGAL_GOLDEN_REPORT_PATH: Path = Path("./legal-golden/reports/latest.json")
    KNOWLEDGE_STORAGE_PATH: Path = Path("./storage/knowledge-sources")
    MAX_UPLOAD_BYTES: int = 52_428_800

    BACKEND_API_BASE_URL: str = "http://127.0.0.1:8000/api/v1"
    AI_AGENT_INTERNAL_TOKEN: str = ""
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_CALLBACK_URL: str | None = None
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    EVIDENCE_LOCAL_STORAGE_PATH: Path = Path("./storage/evidence")
    EVIDENCE_ENCRYPTION_KEY: str | None = None
    EVIDENCE_AUDIT_SIGNING_KEY: str | None = None
    EVIDENCE_MAX_FILE_SIZE_BYTES: int = 10_485_760
    EVIDENCE_S3_BUCKET: str | None = None
    EVIDENCE_S3_PREFIX: str = "evidence-vault"
    REPORT_DELIVERY_EXPORT_PATH: Path = Path("./storage/report-delivery")
    DELIVERY_API_BEARER_TOKEN: str | None = None
    DELIVERY_EMAIL_WEBHOOK_URL: str | None = None
    DELIVERY_EMAIL_WEBHOOK_TOKEN: str | None = None
    DELIVERY_MTLS_PROXY_URL: str | None = None
    DELIVERY_API_TIMEOUT_MS: int = 30_000
    AUTH_RESET_EMAIL_WEBHOOK_URL: str | None = None
    AUTH_RESET_EMAIL_WEBHOOK_TOKEN: str | None = None
    AUTH_RESET_OUTBOX_PATH: Path = Path("./storage/auth-recovery")
    CONTENT_RESOURCE_STORAGE_PATH: Path = Path("./storage/content-resources")
    CONTENT_RESOURCE_MAX_FILE_SIZE_BYTES: int = 52_428_800
    MICRO_EDUCATION_IMAGE_STORAGE_PATH: Path = Path("./storage/microeducation-images")
    MICRO_EDUCATION_IMAGE_MAX_FILE_SIZE_BYTES: int = 10_485_760
    MICRO_EDUCATION_S3_BUCKET: str | None = None
    MICRO_EDUCATION_S3_PREFIX: str = "microeducation-images"
    MICRO_EDUCATION_CDN_BASE_URL: str | None = None
    MEDIA_ASSET_STORAGE_PATH: Path = Path("./storage/media-assets")
    MEDIA_ASSET_MAX_FILE_SIZE_BYTES: int = 2_097_152
    AI_AGENT_BASE_URL: str = "http://127.0.0.1:8000/api/v1"
    SCAMSHIELD_URLHAUS_AUTH_KEY: str | None = None
    SCAMSHIELD_SAFE_BROWSING_API_KEY: str | None = None
    RAG_VECTOR_INDEX: str = "rag_chunks_vector_index"
    RAG_VECTOR_PROVIDER: str = "pinecone"
    RAG_MIN_SCORE_SUPPORT: float = 0.68
    RAG_TOP_K_SUPPORT: int = 5
    INTERNAL_KNOWLEDGE_DIR: Path = Path("knowledge/internal")
    ENABLE_INTERNAL_KNOWLEDGE_AUTO_APPROVE: bool = True
    ENABLE_ADMIN_SEED: bool = False
    DEFAULT_SUPER_ADMIN_EMAIL: str | None = None
    DEFAULT_SUPER_ADMIN_PASSWORD: str | None = None
    DEFAULT_SUPER_ADMIN_FULL_NAME: str = "SafeSpeak Super Admin"

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

    def validate_production_secrets(self) -> None:
        if self.ENVIRONMENT != "production":
            return
        required = {
            "JWT_ACCESS_SECRET": self.JWT_ACCESS_SECRET,
            "JWT_REFRESH_SECRET": self.JWT_REFRESH_SECRET,
            "EVIDENCE_ENCRYPTION_KEY": self.EVIDENCE_ENCRYPTION_KEY,
            "EVIDENCE_AUDIT_SIGNING_KEY": self.EVIDENCE_AUDIT_SIGNING_KEY,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing production secrets: " + ", ".join(sorted(missing))
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
