import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import error_response

logger = logging.getLogger("safespeak.errors")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_code_for_status(status_code: int) -> str:
    if status_code in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_409_CONFLICT,
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    }:
        return "VALIDATION_ERROR"
    if status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        return "AUTH_ERROR"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "NOT_FOUND"
    return "INTERNAL_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return ORJSONResponse(
            error_response(
                str(exc.detail),
                error_code=_error_code_for_status(exc.status_code),
                request_id=_request_id(request),
            ),
            status_code=exc.status_code,
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ):
        return ORJSONResponse(
            error_response(
                str(exc.detail),
                error_code=_error_code_for_status(exc.status_code),
                request_id=_request_id(request),
            ),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return ORJSONResponse(
            error_response(
                "Validation failed",
                error_code="VALIDATION_ERROR",
                request_id=_request_id(request),
                errors=exc.errors(),
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "Unhandled application error",
            extra={"request_id": _request_id(request), "path": request.url.path},
            exc_info=exc,
        )
        return ORJSONResponse(
            error_response(
                "Internal server error",
                error_code="INTERNAL_ERROR",
                request_id=_request_id(request),
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
