from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.assistant_graph import run_timeline_assistant
from app.agents.rag_graph import answer_question
from app.core.responses import success
from app.core.security import Principal, require_ai_consent
from app.models.common import AnswerInput, SearchInput, TimelineAssistantInput
from app.services.legal_readiness import assert_legal_runtime_ready
from app.services.retrieval import hybrid_search

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search")
async def search(
    request: SearchInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    assert_legal_runtime_ready()
    results = await hybrid_search(request)
    return success(
        "RAG search completed",
        {"results": results},
        {"informationOnly": True, "citationsRequired": True},
    )


@router.post("/answer")
async def answer(
    request: AnswerInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    assert_legal_runtime_ready()
    result = await answer_question(request)
    return success("RAG answer generated", result, {"informationOnly": True})


@router.post("/timeline-assistant")
async def timeline_assistant(
    request: TimelineAssistantInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    assert_legal_runtime_ready()
    result = await run_timeline_assistant(request)
    return success(
        "Timeline assistant response generated",
        result,
        {"informationOnly": True},
    )
