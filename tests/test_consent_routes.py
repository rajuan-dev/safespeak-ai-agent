from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.consent import service as consent_service_module


class FakeConsentRepository:
    def __init__(self) -> None:
        self.history = []

    async def find_latest(self, owner):
        return self.history[-1] if self.history else None

    async def find_history(self, owner):
        return list(reversed(self.history))

    async def create_record(self, payload):
        record = {
            "_id": f"507f1f77bcf86cd79943908{len(self.history)}",
            **payload,
        }
        self.history.append(record)
        return record


@pytest.fixture
def fake_consent_repo(monkeypatch):
    repository = FakeConsentRepository()

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(consent_service_module, "get_consent_repository", lambda: repository)
    monkeypatch.setattr(consent_service_module, "create_audit_log", noop_audit)
    yield repository


@pytest.fixture
def fake_session(monkeypatch):
    async def fake_get_session_by_token(_token: str):
        return SimpleNamespace(id="507f1f77bcf86cd799439055", user_id=None)

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_create_and_update_consent(fake_consent_repo, fake_session):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/consents/update",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"flags": {"process_with_ai": True}, "source": "user"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["consent"]["process_with_ai"] is True


def test_withdraw_consent(fake_consent_repo, fake_session):
    with TestClient(app) as client:
        client.post(
            "/api/v1/consents/update",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"flags": {"cloud_sync": True}, "source": "user"},
        )
        response = client.post(
            "/api/v1/consents/withdraw",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"flags": ["cloud_sync"], "source": "withdrawal"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["consent"]["cloud_sync"] is False


def test_consent_history(fake_consent_repo, fake_session):
    with TestClient(app) as client:
        client.post(
            "/api/v1/consents/update",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"flags": {"process_with_ai": True}, "source": "user"},
        )
        response = client.get(
            "/api/v1/consents/history",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert response.status_code == 200
    assert len(response.json()["data"]["history"]) == 1
