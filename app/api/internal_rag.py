from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.responses import success
from app.core.security import require_internal_service
from app.modules.rag.schema import AnswerInput, SearchInput, TimelineAssistantInput
from app.modules.rag.service import answer_rag, search_rag, timeline_assistant_rag

router = APIRouter(prefix="/internal/rag", tags=["internal-rag"])


@router.post("/search")
async def internal_search(
    request: SearchInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    return success(
        "RAG search completed",
        {"results": await search_rag(request)},
        {"informationOnly": True, "citationsRequired": True},
    )


@router.post("/answer")
async def internal_answer(
    request: AnswerInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    return success("RAG answer generated", await answer_rag(request), {"informationOnly": True})


@router.post("/timeline-assistant")
async def internal_timeline_assistant(
    request: TimelineAssistantInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    result = await timeline_assistant_rag(request)
    return success(
        "Timeline assistant response generated",
        result,
        {"informationOnly": True},
    )
