from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import ai, extraction, health, knowledge, rag
from app.core.config import get_settings
from app.core.database import close_database
from app.core.responses import failure
from app.services.knowledge import ensure_indexes
from app.services.legal_readiness import legal_runtime_health


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_indexes()
    settings = get_settings()
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


settings = get_settings()
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    code = (
        "AUTH_ERROR"
        if exc.status_code in {401, 403}
        else "NOT_FOUND"
        if exc.status_code == 404
        else "VALIDATION_ERROR"
        if exc.status_code in {400, 409, 413, 422}
        else "INTERNAL_ERROR"
    )
    return ORJSONResponse(
        failure(
            str(exc.detail),
            error_code=code,
            request_id=getattr(request.state, "request_id", None),
        ),
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return ORJSONResponse(
        failure(
            "Validation failed",
            error_code="VALIDATION_ERROR",
            request_id=getattr(request.state, "request_id", None),
            errors=exc.errors(),
        ),
        status_code=400,
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, _exc: Exception):
    return ORJSONResponse(
        failure(
            "Internal server error",
            error_code="INTERNAL_ERROR",
            request_id=getattr(request.state, "request_id", None),
        ),
        status_code=500,
    )


app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(extraction.router, prefix=settings.API_PREFIX)
app.include_router(rag.router, prefix=settings.API_PREFIX)
app.include_router(knowledge.router, prefix=settings.API_PREFIX)
app.include_router(ai.router, prefix=settings.API_PREFIX)
