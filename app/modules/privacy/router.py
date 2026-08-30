from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import CreatePrivacyRequestInput, DeleteRequestInput
from .service import (
    create_deletion_request,
    create_privacy_request,
    get_own_privacy_request,
    get_privacy_export,
    list_own_privacy_requests,
)

privacy_requests_router = APIRouter(prefix="/privacy-requests", tags=["privacy"])
privacy_router = APIRouter(prefix="/privacy", tags=["privacy"])


def _context(request: Request, principal: AuthenticatedSessionOrUser) -> dict:
    return {
        "owner": {"userId": principal.user_id, "sessionId": principal.session_id},
        "ip": request.client.host if request.client else None,
        "userAgent": request.headers.get("user-agent"),
        "exportedAt": datetime.now(UTC).isoformat(),
    }


@privacy_requests_router.post("/", status_code=201)
async def create_privacy_request_route(
    request: Request,
    input_data: CreatePrivacyRequestInput,
    principal: AuthenticatedSessionOrUser,
):
    created = await create_privacy_request(_context(request, principal), input_data)
    return success("Privacy request created", {"request": created})


@privacy_requests_router.get("/me")
async def list_own_privacy_requests_route(
    request: Request,
    principal: AuthenticatedSessionOrUser,
):
    requests = await list_own_privacy_requests(_context(request, principal))
    return success("Privacy requests retrieved", {"requests": requests})


@privacy_requests_router.get("/{id}")
async def get_own_privacy_request_route(
    request: Request,
    id: str,
    principal: AuthenticatedSessionOrUser,
):
    record = await get_own_privacy_request(_context(request, principal), id)
    return success("Privacy request retrieved", {"request": record})


@privacy_router.get("/export")
async def privacy_export_route(request: Request, principal: AuthenticatedSessionOrUser):
    export_payload = await get_privacy_export(_context(request, principal))
    return success("Privacy export generated", {"export": export_payload})


@privacy_router.post("/delete-request", status_code=201)
async def delete_request_route(
    request: Request,
    input_data: DeleteRequestInput,
    principal: AuthenticatedSessionOrUser,
):
    created = await create_deletion_request(_context(request, principal), input_data)
    return success("Deletion request created", {"request": created})
