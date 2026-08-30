import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import require_ai_consent
from app.modules.auth.dependencies import Principal
from app.modules.rag import dependencies as rag_dependencies_module
from app.modules.rag.router import router

rag_router_module = importlib.import_module("app.modules.rag.router")


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[require_ai_consent] = lambda: Principal(
        actor_type="user",
        user_id="507f1f77bcf86cd799439011",
        role="public_user",
    )
    app.dependency_overrides[rag_dependencies_module.current_rag_admin] = lambda: Principal(
        actor_type="user",
        user_id="507f1f77bcf86cd799439012",
        role="content_admin",
    )
    return TestClient(app)


def test_search_route_returns_expected_envelope(monkeypatch):
    async def fake_search(request):
        return [{"chunkId": "1", "title": "Example Act"}]

    monkeypatch.setattr(rag_router_module, "search_rag", fake_search)
    response = build_client().post("/api/v1/rag/search", json={"query": "reporting duty"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "RAG search completed"
    assert payload["meta"] == {"informationOnly": True, "citationsRequired": True}
    assert payload["data"]["results"][0]["chunkId"] == "1"


def test_answer_route_returns_grounded_response(monkeypatch):
    async def fake_answer(request):
        return {"answer": "Use approved sources only.", "citations": [{"sourceId": "1"}]}

    monkeypatch.setattr(rag_router_module, "answer_rag", fake_answer)
    response = build_client().post(
        "/api/v1/rag/answer",
        json={"query": "what is the rule", "question": "what is the rule"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "RAG answer generated"
    assert response.json()["data"]["answer"] == "Use approved sources only."


def test_debug_retrieve_route_returns_admin_debug(monkeypatch):
    async def fake_debug(request):
        return {"resultCount": 1, "results": [{"chunkId": "1"}]}

    monkeypatch.setattr(rag_router_module, "debug_retrieve_rag", fake_debug)
    response = build_client().post(
        "/api/v1/rag/debug/retrieve",
        json={"query": "privacy", "topK": 3},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "RAG debug retrieval completed"


def test_status_route_returns_status(monkeypatch):
    async def fake_status(source_id):
        return {"sourceId": source_id, "ingestionStatus": "embedded", "ocrStatus": "completed"}

    monkeypatch.setattr(rag_router_module, "get_knowledge_source_status", fake_status)
    response = build_client().get("/api/v1/rag/knowledge-sources/507f1f77bcf86cd799439211/status")
    assert response.status_code == 200
    assert response.json()["data"]["status"]["ingestionStatus"] == "embedded"
