from fastapi import APIRouter, Request, status

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import AppendConversationFlowMessageInput, CreateConversationFlowSessionInput
from .service import (
    append_conversation_flow_message,
    create_conversation_flow_session,
    get_conversation_flow_details,
    get_conversation_flow_recommendations,
    get_conversation_flow_session,
    get_conversation_flow_support,
    get_conversation_flow_triage,
)

router = APIRouter(prefix="/conversation-flow", tags=["conversation-flow"])


def _context(request: Request, principal: AuthenticatedSessionOrUser) -> dict:
    return {
        "owner": {"userId": principal.user_id, "sessionId": principal.session_id},
        "ip": request.client.host if request.client else None,
        "userAgent": request.headers.get("user-agent"),
    }


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_conversation_flow_session_route(
    request: Request,
    input_data: CreateConversationFlowSessionInput,
    principal: AuthenticatedSessionOrUser,
):
    payload = await create_conversation_flow_session(_context(request, principal), input_data)
    return success("Conversation session created", payload)


@router.get("/sessions/{id}")
async def get_conversation_flow_session_route(
    request: Request,
    id: str,
    principal: AuthenticatedSessionOrUser,
):
    payload = await get_conversation_flow_session(_context(request, principal), id)
    return success("Conversation session retrieved", payload)


@router.post("/sessions/{id}/messages")
async def append_conversation_flow_message_route(
    request: Request,
    id: str,
    input_data: AppendConversationFlowMessageInput,
    principal: AuthenticatedSessionOrUser,
):
    payload = await append_conversation_flow_message(_context(request, principal), id, input_data)
    return success("Conversation turn recorded", payload)


@router.get("/sessions/{id}/triage")
async def get_conversation_flow_triage_route(
    request: Request,
    id: str,
    principal: AuthenticatedSessionOrUser,
):
    payload = await get_conversation_flow_triage(_context(request, principal), id)
    return success("Conversation triage retrieved", payload)


@router.get("/sessions/{id}/support")
async def get_conversation_flow_support_route(
    request: Request,
    id: str,
    principal: AuthenticatedSessionOrUser,
):
    payload = await get_conversation_flow_support(_context(request, principal), id)
    return success("Conversation support bundle retrieved", payload)


@router.get("/sessions/{id}/recommendations")
async def get_conversation_flow_recommendations_route(
    request: Request,
    id: str,
    principal: AuthenticatedSessionOrUser,
):
    payload = await get_conversation_flow_recommendations(_context(request, principal), id)
    return success("Conversation recommendations retrieved", payload)


@router.get("/sessions/{id}/details")
async def get_conversation_flow_details_route(
    request: Request,
    id: str,
    principal: AuthenticatedSessionOrUser,
):
    payload = await get_conversation_flow_details(_context(request, principal), id)
    return success("Conversation details retrieved", payload)
