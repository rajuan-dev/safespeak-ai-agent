from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.assistant_graph import run_timeline_assistant
from app.agents.rag_graph import answer_question
from app.core.responses import success
from app.core.security import require_internal_service
from app.models.common import AnswerInput, SearchInput, TimelineAssistantInput
from app.services.legal_readiness import assert_legal_runtime_ready
from app.services.retrieval import hybrid_search

router = APIRouter(prefix="/internal/rag", tags=["internal-rag"])


@router.post("/search")
async def internal_search(
    request: SearchInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    assert_legal_runtime_ready()
    results = await hybrid_search(request)
    return success(
        "RAG search completed",
        {"results": results},
        {"informationOnly": True, "citationsRequired": True},
    )


@router.post("/answer")
async def internal_answer(
    request: AnswerInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    assert_legal_runtime_ready()
    result = await answer_question(request)
    return success("RAG answer generated", result, {"informationOnly": True})


@router.post("/timeline-assistant")
async def internal_timeline_assistant(
    request: TimelineAssistantInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    result = await run_timeline_assistant(request)
    return success(
        "Timeline assistant response generated",
        result,
        {"informationOnly": True},
    )
