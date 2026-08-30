from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ai import router
from app.core.security import (
    Principal,
    require_ai_consent,
    require_ai_or_transcription_consent,
)
from app.modules.ai import service as ai_service_module
from app.modules.ai.schema import (
    ClarifyingQuestionsInput,
    RedactInput,
    SynthesizeSpeechInput,
    TranslateInput,
    TriageInput,
)


class FakeAiRepository:
    async def find_owned_report(self, principal, report_id):
        return None

    async def list_report_evidence(self, principal, report_id):
        return []

    async def get_public_platform_settings(self):
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

    async def create_ai_interaction(self, **kwargs):
        return {"_id": "1", **kwargs}


class FakeLlm:
    async def json_completion(self, **kwargs):
        user = kwargs["user"]
        if "Target language" in user:
            return {
                "translatedText": "hola",
                "sourceLanguage": "English",
                "targetLanguage": "Spanish",
                "reviewStatus": "generated",
            }
        if "Generate as many trauma-informed clarifying questions" in kwargs["system"]:
            return {
                "questions": ["What happened first?"],
                "rationale": "Need sequence",
                "reviewStatus": "generated",
            }
        if "Triage this report" in kwargs["system"]:
            return {
                "severitySignal": "medium",
                "summary": "A coworker shared private health information.",
                "assessmentBody": "This may need workplace support and documentation.",
                "confidence": "medium",
                "suggestedSupportCategories": ["workplace_support"],
                "recommendedActions": ["Write down what was shared and when."],
                "reviewStatus": "generated",
            }
        return {"summary": "ok", "reviewStatus": "generated"}


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[require_ai_consent] = lambda: Principal(
        actor_type="user",
        user_id="507f1f77bcf86cd799439011",
        role="public_user",
    )
    app.dependency_overrides[require_ai_or_transcription_consent] = lambda: Principal(
        actor_type="user",
        user_id="507f1f77bcf86cd799439011",
        role="public_user",
    )
    return TestClient(app)


async def test_triage_service_sets_guardrails_and_logs():
    result = await ai_service_module.triage_report(
        TriageInput(narrative="My coworker shared my health details without consent."),
        Principal(actor_type="user", user_id="507f1f77bcf86cd799439011"),
        repository=FakeAiRepository(),
        llm=FakeLlm(),
    )
    assert result["reviewStatus"] == "pending_human_review"
    assert result["guardrails"]["informationOnly"] is True
    assert result["templateStatus"] == "approved"


async def test_translate_service_preserves_nested_interaction_shape():
    result = await ai_service_module.translate(
        TranslateInput(text="hello", targetLanguage="Spanish"),
        Principal(actor_type="user", user_id="507f1f77bcf86cd799439011"),
        repository=FakeAiRepository(),
        llm=FakeLlm(),
    )
    assert result["output"]["translatedText"] == "hola"
    assert result["reviewStatus"] == "pending_human_review"


def test_redact_service_masks_email_and_phone():
    result = ai_service_module.redact_pii(
        RedactInput(text="Email me at test@example.com or call 0412345678"),
        repository=FakeAiRepository(),
    )
    assert "[EMAIL]" in result["output"]["redactedText"]
    assert "[PHONE]" in result["output"]["redactedText"]


async def test_conversation_response_uses_ai_when_consent_present():
    result = await ai_service_module.generate_conversation_response(
        session={"selectedTopic": "general_support", "latestTurnRiskLevel": "low"},
        messages=[{"role": "user", "content": "I feel unsafe at work"}],
        latest_user_message="I feel unsafe at work",
        language="en",
        consent={"process_with_ai": True, "store_local": True},
        repository=FakeAiRepository(),
        llm=FakeLlm(),
    )
    assert result["responseSource"] == "conversation_flow_ai"
    assert result["assistantLanguage"] == "en"


async def test_conversation_response_falls_back_without_ai_consent():
    result = await ai_service_module.generate_conversation_response(
        session={"selectedTopic": "general_support", "latestTurnRiskLevel": "low"},
        messages=[{"role": "user", "content": "I feel unsafe at work"}],
        latest_user_message="I feel unsafe at work",
        language="en",
        consent={"process_with_ai": False, "store_local": True},
        repository=FakeAiRepository(),
        llm=FakeLlm(),
    )
    assert result["responseSource"] == "conversation_flow_rule_based"


def test_triage_route_returns_expected_message_meta(monkeypatch):
    async def fake_triage(request, principal):
        return {"summary": "ok", "reviewStatus": "pending_human_review"}

    monkeypatch.setattr("app.api.ai.triage_report", fake_triage)
    response = build_client().post("/api/v1/ai/triage-report", json={"narrative": "test"})
    assert response.status_code == 200
    assert response.json()["message"] == "Report triaged"
    assert response.json()["meta"] == {"informationOnly": True}


async def test_clarifying_questions_uses_backend_limit():
    result = await ai_service_module.clarifying_questions(
        ClarifyingQuestionsInput(narrative="Someone threatened me.", maxQuestions=25),
        Principal(actor_type="user", user_id="507f1f77bcf86cd799439011"),
        repository=FakeAiRepository(),
        llm=FakeLlm(),
    )
    assert result["reviewStatus"] == "pending_human_review"


def test_synthesize_speech_request_defaults():
    request = SynthesizeSpeechInput(text="hello")
    assert request.voice is None
