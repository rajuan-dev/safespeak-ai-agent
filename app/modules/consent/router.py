from fastapi import APIRouter, Request

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import UpdateConsentInput, WithdrawConsentInput
from .service import (
    get_consent_history,
    get_current_consent,
    update_consent,
    withdraw_consent,
)

router = APIRouter(prefix="/consents", tags=["consent"])


def _owner(principal: AuthenticatedSessionOrUser) -> dict[str, str | None]:
    return {"userId": principal.user_id, "sessionId": principal.session_id}


@router.get("/current")
async def get_current_consent_route(principal: AuthenticatedSessionOrUser):
    consent = await get_current_consent(_owner(principal))
    return success("Current consent retrieved", {"consent": consent})


@router.post("/update")
async def update_consent_route(
    request: Request,
    input_data: UpdateConsentInput,
    principal: AuthenticatedSessionOrUser,
):
    consent = await update_consent(
        _owner(principal),
        input_data,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success("Consent updated", {"consent": consent})


@router.post("/withdraw")
async def withdraw_consent_route(
    request: Request,
    input_data: WithdrawConsentInput,
    principal: AuthenticatedSessionOrUser,
):
    consent = await withdraw_consent(
        _owner(principal),
        input_data,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success("Consent withdrawn", {"consent": consent})


@router.get("/history")
async def get_consent_history_route(principal: AuthenticatedSessionOrUser):
    history = await get_consent_history(_owner(principal))
    return success("Consent history retrieved", {"history": history})
