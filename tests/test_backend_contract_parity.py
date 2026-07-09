import pytest
from pydantic import ValidationError

from app.models.ai import (
    ClarifyingQuestionsInput,
    RedactInput,
    SynthesizeSpeechInput,
    TranslateInput,
    TriageInput,
)
from app.services.ai_tools import clarifying_questions, synthesize_speech, triage_report


def test_ai_agent_accepts_backend_clarifying_question_limit():
    request = ClarifyingQuestionsInput(narrative="A short report", maxQuestions=25)

    assert request.maxQuestions == 25


def test_ai_agent_rejects_questions_above_backend_limit():
    with pytest.raises(ValidationError):
        ClarifyingQuestionsInput(narrative="A short report", maxQuestions=26)


def test_ai_agent_uses_backend_translate_default_language():
    request = TranslateInput(text="hello")

    assert request.targetLanguage == "English"


def test_ai_agent_matches_backend_text_length_limit():
    TranslateInput(text="x" * 12_000)
    RedactInput(text="x" * 12_000)

    with pytest.raises(ValidationError):
        TranslateInput(text="x" * 12_001)


async def test_interaction_wrapper_uses_backend_pending_human_review(monkeypatch):
    async def fake_completion(*, system, user, fallback):
        return {"questions": ["What happened?"], "reviewStatus": "generated"}

    monkeypatch.setattr("app.services.ai_tools.llm_service.json_completion", fake_completion)

    result = await clarifying_questions(
        ClarifyingQuestionsInput(narrative="Someone threatened me.")
    )

    assert result["reviewStatus"] == "pending_human_review"
    assert result["guardrails"]["informationOnly"] is True
    assert result["guardrails"]["requiresHumanReview"] is True
    assert "legalAdviceDisclaimer" in result["guardrails"]


async def test_triage_report_normalizes_backend_safety_flags(monkeypatch):
    async def fake_completion(*, system, user, fallback):
        return {
            "severitySignal": "low",
            "summary": "You can sue and you will win.",
            "assessmentBody": "This is definitely illegal.",
            "confidence": "high",
        }

    async def fake_platform_settings():
        return {
            "ai": {
                "disclaimerText": (
                    "This output is information-only and must not be treated as legal, "
                    "medical, counselling, crisis, or case-management advice."
                ),
                "humanReviewText": (
                    "AI-generated content may require human review before use in formal reports."
                ),
                "triageFallbackText": (
                    "SafeSpeak cannot confidently triage this with the available information."
                ),
                "triageTemplateStatus": "approved",
                "triageSystemPrompt": "prompt",
                "triageResponseTemplate": "template",
            },
            "version": 1,
        }

    monkeypatch.setattr("app.services.ai_tools.llm_service.json_completion", fake_completion)
    monkeypatch.setattr("app.services.ai_tools._get_public_platform_settings", fake_platform_settings)

    result = await triage_report(
        TriageInput(narrative="My boss shared my health info with coworkers.")
    )

    assert result["reviewStatus"] == "pending_human_review"
    assert result["fallbackReason"] == "legal_advice_risk"
    assert result["pendingHumanReview"] is True
    assert result["confidence"] == "low"
    assert result["safetyFlags"]["legalAdviceRisk"] is True
    assert result["guardrails"]["requiresHumanReview"] is True


def test_synthesize_speech_model_matches_backend_limit():
    request = SynthesizeSpeechInput(text="hello")

    assert request.voice is None


async def test_synthesize_speech_uses_backend_temporary_audio_shape(monkeypatch):
    class FakeResponse:
        status_code = 200
        content = b"fake-mp3"

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.ai_tools.httpx.AsyncClient",
        lambda timeout: FakeAsyncClient(),
    )
    monkeypatch.setattr(
        "app.services.ai_tools.get_settings",
        lambda: type(
            "S",
            (),
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_TTS_MODEL": "gpt-4o-mini-tts",
                "OPENAI_TTS_VOICE": "alloy",
            },
        )(),
    )

    result = await synthesize_speech(SynthesizeSpeechInput(text="Hello world"))

    assert result["mimeType"] == "audio/mpeg"
    assert result["model"] == "gpt-4o-mini-tts"
    assert result["voice"] == "alloy"
    assert result["temporary"] is True
    assert isinstance(result["audioBase64"], str)
