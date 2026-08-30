import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import ai, extraction, health, internal_ai, internal_rag
from app.config.database import close_database
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_http_middleware
from app.database.indexes import ensure_all_indexes
from app.modules.admin.router import router as admin_router
from app.modules.analytics.router import admin_router as admin_analytics_router
from app.modules.analytics.router import router as analytics_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import google_router as legacy_google_auth_router
from app.modules.auth.router import router as auth_router
from app.modules.consent.router import router as consent_router
from app.modules.content.router import (
    admin_content_resources_router,
    admin_microeducation_router,
    content_resources_router,
)
from app.modules.content_pages.router import admin_router as admin_content_pages_router
from app.modules.content_pages.router import router as content_pages_router
from app.modules.conversation_flow.router import router as conversation_flow_router
from app.modules.evidence.router import router as evidence_router
from app.modules.feedback.router import admin_router as admin_feedback_router
from app.modules.feedback.router import router as feedback_router
from app.modules.media_assets.router import admin_router as admin_media_assets_router
from app.modules.media_assets.router import router as media_assets_router
from app.modules.notifications.router import router as notifications_router
from app.modules.platform_settings.router import admin_router as admin_platform_settings_router
from app.modules.platform_settings.router import router as platform_settings_router
from app.modules.privacy.router import privacy_requests_router, privacy_router
from app.modules.profiles.router import router as profiles_router
from app.modules.rag.router import router as rag_router
from app.modules.reports.router import router as reports_router
from app.modules.resources.router import admin_router as admin_resources_router
from app.modules.resources.router import router as resources_router
from app.modules.scamshield.router import router as scamshield_router
from app.modules.scope.router import router as scope_router
from app.modules.sessions.router import router as sessions_router
from app.modules.support.router import router as support_router
from app.modules.taxonomies.router import router as taxonomies_router
from app.services.knowledge import ensure_indexes
from app.services.legal_readiness import legal_runtime_health


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.validate_production_secrets()
    if os.getenv("SAFESPEAK_SKIP_STARTUP_INDEXES", "").lower() not in {"1", "true", "yes"}:
        await ensure_all_indexes()
        await ensure_indexes()
    legal_health = legal_runtime_health()
    if (
        settings.ENVIRONMENT == "production"
        and settings.LEGAL_FAIL_CLOSED_ON_STARTUP
        and not legal_health["ready"]
    ):
        raise RuntimeError(
            f"Legal production readiness failed: {', '.join(legal_health['blockers'])}"
        )
    yield
    await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    register_http_middleware(app)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(health.router, prefix=settings.API_PREFIX)
    app.include_router(extraction.router, prefix=settings.API_PREFIX)
    app.include_router(rag_router, prefix=settings.API_PREFIX)
    app.include_router(ai.router, prefix=settings.API_PREFIX)
    app.include_router(internal_ai.router, prefix=settings.API_PREFIX)
    app.include_router(internal_rag.router, prefix=settings.API_PREFIX)
    app.include_router(analytics_router, prefix=settings.API_PREFIX)
    app.include_router(admin_analytics_router, prefix=settings.API_PREFIX)
    app.include_router(sessions_router, prefix=settings.API_PREFIX)
    app.include_router(auth_router, prefix=settings.API_PREFIX)
    app.include_router(consent_router, prefix=settings.API_PREFIX)
    app.include_router(conversation_flow_router, prefix=settings.API_PREFIX)
    app.include_router(admin_router, prefix=settings.API_PREFIX)
    app.include_router(audit_router, prefix=settings.API_PREFIX)
    app.include_router(taxonomies_router, prefix=settings.API_PREFIX)
    app.include_router(resources_router, prefix=settings.API_PREFIX)
    app.include_router(admin_resources_router, prefix=settings.API_PREFIX)
    app.include_router(platform_settings_router, prefix=settings.API_PREFIX)
    app.include_router(admin_platform_settings_router, prefix=settings.API_PREFIX)
    app.include_router(scope_router, prefix=settings.API_PREFIX)
    app.include_router(notifications_router, prefix=settings.API_PREFIX)
    app.include_router(content_pages_router, prefix=settings.API_PREFIX)
    app.include_router(admin_content_pages_router, prefix=settings.API_PREFIX)
    app.include_router(content_resources_router, prefix=settings.API_PREFIX)
    app.include_router(admin_content_resources_router, prefix=settings.API_PREFIX)
    app.include_router(admin_microeducation_router, prefix=settings.API_PREFIX)
    app.include_router(media_assets_router, prefix=settings.API_PREFIX)
    app.include_router(admin_media_assets_router, prefix=settings.API_PREFIX)
    app.include_router(feedback_router, prefix=settings.API_PREFIX)
    app.include_router(admin_feedback_router, prefix=settings.API_PREFIX)
    app.include_router(profiles_router, prefix=settings.API_PREFIX)
    app.include_router(privacy_requests_router, prefix=settings.API_PREFIX)
    app.include_router(privacy_router, prefix=settings.API_PREFIX)
    app.include_router(reports_router, prefix=settings.API_PREFIX)
    app.include_router(evidence_router, prefix=settings.API_PREFIX)
    app.include_router(scamshield_router, prefix=settings.API_PREFIX)
    app.include_router(support_router, prefix=settings.API_PREFIX)
    app.include_router(legacy_google_auth_router, prefix="/api")
    return app


app = create_app()
