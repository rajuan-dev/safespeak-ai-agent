from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.internal_ai import router
from app.core.security import require_internal_service


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[require_internal_service] = lambda: None
    return TestClient(app)


def test_internal_completion_preserves_model_and_response_envelope(monkeypatch):
    captured = {}

    async def fake_text_completion(**kwargs):
        captured.update(kwargs)
        return "generated reply"

    monkeypatch.setattr("app.api.internal_ai.llm_service.text_completion", fake_text_completion)

    response = build_client().post(
        "/api/v1/internal/ai/complete",
        json={
            "systemPrompt": "System rules",
            "userPrompt": "Hello",
            "model": "test-model",
            "temperature": 0.1,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"text": "generated reply"}
    assert captured["model"] == "test-model"


def test_internal_json_completion_returns_nested_result(monkeypatch):
    async def fake_json_completion(**_kwargs):
        return {"assistantMessage": "grounded reply"}

    monkeypatch.setattr("app.api.internal_ai.llm_service.json_completion", fake_json_completion)

    response = build_client().post(
        "/api/v1/internal/ai/complete-json",
        json={"systemPrompt": "System rules", "userPrompt": "Hello"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["result"] == {"assistantMessage": "grounded reply"}


def test_internal_embeddings_preserve_vector_count(monkeypatch):
    async def fake_embed(texts, model=None):
        assert model == "embedding-model"
        return [[float(index)] for index, _text in enumerate(texts)]

    monkeypatch.setattr("app.api.internal_ai.embedding_service.embed", fake_embed)

    response = build_client().post(
        "/api/v1/internal/ai/embeddings",
        json={"texts": ["one", "two"], "model": "embedding-model"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["embeddings"] == [[0.0], [1.0]]


def test_internal_vision_returns_text(monkeypatch):
    async def fake_vision_text_completion(**kwargs):
        assert kwargs["model"] == "vision-model"
        return "visible text"

    monkeypatch.setattr(
        "app.api.internal_ai.llm_service.vision_text_completion",
        fake_vision_text_completion,
    )

    response = build_client().post(
        "/api/v1/internal/ai/vision-text",
        json={
            "instruction": "Extract text",
            "imageData": "data:image/png;base64,abc",
            "model": "vision-model",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"text": "visible text"}
