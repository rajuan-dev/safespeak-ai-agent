from fastapi import HTTPException, status

from app.agents import assistant_graph
from app.agents.assistant_graph import run_timeline_assistant
from app.models.common import TimelineAssistantInput


async def test_timeline_assistant_degrades_when_legal_rag_is_unavailable(monkeypatch):
    def unavailable_legal_runtime() -> None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Legal RAG unavailable")

    async def fail_if_retrieved(_search):
        raise AssertionError("legal retrieval should not run when readiness fails")

    async def fake_completion(*, system, user, fallback):
        assert "Optional approved context:" in user
        return {
            **fallback,
            "assistantMessage": "I can help organise this without legal sources for now.",
            "confidence": "medium",
        }

    monkeypatch.setattr(assistant_graph, "assert_legal_runtime_ready", unavailable_legal_runtime)
    monkeypatch.setattr(assistant_graph, "hybrid_search", fail_if_retrieved)
    monkeypatch.setattr(assistant_graph.llm_service, "json_completion", fake_completion)

    result = await run_timeline_assistant(
        TimelineAssistantInput(
            message="What law applies to this report?",
            conversation=[],
            timeline={},
            jurisdiction="NSW",
        )
    )

    assert result["assistantMessage"] == "I can help organise this without legal sources for now."
    assert result["citations"] == []
    assert result["rag"] == {"used": False, "unavailable": True, "resultCount": 0}
    assert result["reviewStatus"] == "generated_with_rag_unavailable"
    assert result["ragStatus"] == "required_but_no_sources_found"
    assert result["responseMode"] == "safespeak_model"
    assert result["guardrailStatus"] == "flagged"
    assert result["fallbackReason"] == "missing_legal_boundary_disclaimer"
    assert result["intent"] == "unknown"
    assert result["turnPolicyDecision"]["ragRequired"] is True
    assert result["turnPolicyDecision"]["ragReason"] == "source_grounded_request"
    assert result["selectedResponseSource"] in {
        "openai_model",
        "openai_model_with_rag",
        "model_empty_fallback",
    }


async def test_timeline_assistant_drops_extra_next_question_when_visible_reply_would_exceed_limit(
    monkeypatch,
):
    def legal_runtime_ready() -> None:
        return None

    async def no_results(_search):
        return []

    async def fake_completion(*, system, user, fallback):
        return {
            **fallback,
            "assistantMessage": "Can you tell me when this happened?",
            "nextQuestion": "What date was it?",
            "confidence": "medium",
        }

    monkeypatch.setattr(assistant_graph, "assert_legal_runtime_ready", legal_runtime_ready)
    monkeypatch.setattr(assistant_graph, "hybrid_search", no_results)
    monkeypatch.setattr(assistant_graph.llm_service, "json_completion", fake_completion)

    result = await run_timeline_assistant(
        TimelineAssistantInput(
            message="He threatened me at work.",
            conversation=[],
            timeline={},
            jurisdiction="NSW",
        )
    )

    assert result["assistantMessage"] == "Can you tell me when this happened?"
    assert result["nextQuestion"] == ""
    assert result["guardrailStatus"] == "passed"
    assert result["fallbackReason"] is None
