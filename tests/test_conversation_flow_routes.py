from datetime import UTC, datetime

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.conversation_flow import service as conversation_flow_service_module


def _now() -> datetime:
    return datetime.now(UTC)


class FakeConversationFlowRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.facts: dict[str, dict] = {}
        self.triage: dict[str, dict] = {}

    async def create_session(self, payload):
        session_id = "507f1f77bcf86cd799439211"
        owner = {
            "userId": payload.get("userId"),
            "sessionId": payload.get("sessionId"),
        }
        record = {
            "_id": ObjectId(session_id),
            "createdAt": _now(),
            "updatedAt": _now(),
            **payload,
            **owner,
        }
        self.sessions[session_id] = record
        self.messages[session_id] = []
        return record

    async def find_session_for_owner(self, session_id: str, owner):
        record = self.sessions.get(session_id)
        if not record:
            return None
        if owner.get("userId") and record.get("userId") == owner.get("userId"):
            return record
        if owner.get("sessionId") and record.get("sessionId") == owner.get("sessionId"):
            return record
        return None

    async def update_session(self, session_id: str, owner, updates):
        record = await self.find_session_for_owner(session_id, owner)
        if not record:
            return None
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def create_message(self, payload):
        session_id = str(payload["conversationSessionId"])
        record = {
            "_id": ObjectId(),
            "createdAt": _now(),
            "updatedAt": _now(),
            **payload,
        }
        self.messages.setdefault(session_id, []).append(record)
        return record

    async def list_messages(self, conversation_session_id: str):
        return list(self.messages.get(conversation_session_id, []))

    async def get_facts(self, conversation_session_id: str):
        return self.facts.get(conversation_session_id)

    async def upsert_facts(self, conversation_session_id: str, payload):
        record = {
            "_id": ObjectId(),
            "conversationSessionId": ObjectId(conversation_session_id),
            "createdAt": self.facts.get(conversation_session_id, {}).get("createdAt", _now()),
            "updatedAt": _now(),
            **payload,
        }
        self.facts[conversation_session_id] = record
        return record

    async def get_triage(self, conversation_session_id: str):
        return self.triage.get(conversation_session_id)

    async def upsert_triage(self, conversation_session_id: str, payload):
        record = {
            "_id": ObjectId(),
            "conversationSessionId": ObjectId(conversation_session_id),
            "createdAt": self.triage.get(conversation_session_id, {}).get("createdAt", _now()),
            "updatedAt": _now(),
            **payload,
        }
        self.triage[conversation_session_id] = record
        return record


class FakeAssistant:
    async def respond(self, **kwargs):
        latest_user_message = kwargs["latest_user_message"]
        risk = "high" if "unsafe" in latest_user_message.lower() else "medium"
        return {
            "assistantMessage": "I’m here with you.",
            "nextQuestion": "What feels most important for me to understand next?",
            "confidence": "medium",
            "disclaimer": "This is information only, not legal advice.",
            "intent": "conversation_support",
            "responseMode": "support_victim_style",
            "selectedResponseSource": "test-assistant",
            "responseSource": "test-assistant",
            "reviewStatus": "conversation_support",
            "assistantLanguage": kwargs["language"],
            "triageUpdated": True,
            "latestTurnRiskLevel": risk,
            "activeIncidentRiskLevel": risk,
            "sessionHistoricalMaxRiskLevel": risk,
            "showSources": False,
        }


@pytest.fixture
def fake_conversation_repo(monkeypatch):
    repository = FakeConversationFlowRepository()

    async def fake_consent(owner):
        return {"store_local": True, "cloud_sync": False, "process_with_ai": True}

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        conversation_flow_service_module,
        "get_conversation_flow_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        conversation_flow_service_module, "get_conversation_assistant", lambda: FakeAssistant()
    )
    monkeypatch.setattr(conversation_flow_service_module, "get_current_consent", fake_consent)
    monkeypatch.setattr(conversation_flow_service_module, "create_audit_log", noop_audit)
    return repository


@pytest.fixture
def fake_session(monkeypatch):
    async def fake_get_session_by_token(token: str):
        class Session:
            id = "507f1f77bcf86cd799439299" if token == "anon-token" else "507f1f77bcf86cd799439298"
            user_id = None

        return Session()

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_create_and_get_conversation_session(fake_conversation_repo, fake_session):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/conversation-flow/sessions",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"selectedTopic": "scamshield", "jurisdiction": "NSW"},
        )
        session_id = created.json()["data"]["session"]["id"]
        fetched = client.get(
            f"/api/v1/conversation-flow/sessions/{session_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert created.status_code == 201
    assert fetched.status_code == 200
    assert fetched.json()["data"]["session"]["selectedTopic"] == "scamshield"


def test_append_message_and_retrieve_history(fake_conversation_repo, fake_session):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/conversation-flow/sessions",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"selectedTopic": "general_support"},
        )
        session_id = created.json()["data"]["session"]["id"]
        appended = client.post(
            f"/api/v1/conversation-flow/sessions/{session_id}/messages",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "content": "My manager has been bullying me at work and I feel unsafe.",
                "language": "en",
            },
        )
        fetched = client.get(
            f"/api/v1/conversation-flow/sessions/{session_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert appended.status_code == 200
    assert appended.json()["data"]["transition"]["offerTriage"] is True
    assert len(fetched.json()["data"]["messages"]) == 2
    assert fetched.json()["data"]["factExtraction"]["whatHappened"] is not None


def test_triage_support_recommendations_and_details(fake_conversation_repo, fake_session):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/conversation-flow/sessions",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"selectedTopic": "general_support"},
        )
        session_id = created.json()["data"]["session"]["id"]
        client.post(
            f"/api/v1/conversation-flow/sessions/{session_id}/messages",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "content": "A coworker threatened me at work yesterday and I feel unsafe.",
                "language": "en",
            },
        )
        triage = client.get(
            f"/api/v1/conversation-flow/sessions/{session_id}/triage",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        support = client.get(
            f"/api/v1/conversation-flow/sessions/{session_id}/support",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        recommendations = client.get(
            f"/api/v1/conversation-flow/sessions/{session_id}/recommendations",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        details = client.get(
            f"/api/v1/conversation-flow/sessions/{session_id}/details",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert triage.status_code == 200
    assert triage.json()["data"]["triage"]["likelyCategory"] in {
        "workplace_bullying",
        "harassment",
    }
    assert support.status_code == 200
    assert len(support.json()["data"]["support"]["recommendedActions"]) >= 1
    assert recommendations.status_code == 200
    assert len(recommendations.json()["data"]["recommendations"]) >= 1
    assert details.status_code == 200
    assert (
        details.json()["data"]["details"]["disclaimer"]
        == "This is information only, not legal advice."
    )


def test_owner_and_unauthorized_access(fake_conversation_repo, fake_session):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/conversation-flow/sessions",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"selectedTopic": "general_support"},
        )
        session_id = created.json()["data"]["session"]["id"]
        wrong_owner = client.get(
            f"/api/v1/conversation-flow/sessions/{session_id}",
            headers={"X-SafeSpeak-Session": "other-token"},
        )
        unauthorized = client.get(f"/api/v1/conversation-flow/sessions/{session_id}")
    assert wrong_owner.status_code == 404
    assert unauthorized.status_code == 401
