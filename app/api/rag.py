from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.responses import success
from app.core.security import Principal, require_ai_consent
from app.modules.auth.dependencies import require_admin_role
from app.modules.rag.schema import (
    AnswerInput,
    RagDebugRetrieveInput,
    SearchInput,
    TimelineAssistantInput,
)
from app.modules.rag.service import (
    answer_rag,
    debug_retrieve_rag,
    search_rag,
    timeline_assistant_rag,
)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search")
async def search(
    request: SearchInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "RAG search completed",
        {"results": await search_rag(request)},
        {"informationOnly": True, "citationsRequired": True},
    )


@router.post("/answer")
async def answer(
    request: AnswerInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success("RAG answer generated", await answer_rag(request), {"informationOnly": True})


@router.post("/timeline-assistant")
async def timeline_assistant(
    request: TimelineAssistantInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    result = await timeline_assistant_rag(request)
    return success(
        "Timeline assistant response generated",
        result,
        {"informationOnly": True},
    )


@router.post("/debug/retrieve")
async def debug_retrieve(
    request: RagDebugRetrieveInput,
    _principal: Annotated[Principal, Depends(require_admin_role("super_admin", "content_admin"))],
):
    return success(
        "RAG debug retrieval completed",
        await debug_retrieve_rag(request),
        {"informationOnly": True},
    )
