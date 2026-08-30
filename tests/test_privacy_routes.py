from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.privacy import service as privacy_service_module


class FakePrivacyRepository:
    def __init__(self) -> None:
        self.requests = []
        self.profile = {"preferredLanguage": "en"}
        self.consent_history = [{"_id": "1", "version": 1, "flags": {"store_local": True}}]

    async def create_privacy_request(self, payload):
        record = {
            "_id": f"507f1f77bcf86cd79943909{len(self.requests)}",
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
            **payload,
        }
        self.requests.append(record)
        return record

    async def list_privacy_requests(self, owner):
        return list(reversed(self.requests))

    async def get_privacy_request(self, owner, request_id: str):
        for record in self.requests:
            if record["_id"] == request_id:
                return record
        return None

    async def get_user_for_export(self, user_id: str | None):
        return None

    async def get_anonymous_session_for_export(self, session_id: str | None):
        return {
            "_id": "507f1f77bcf86cd799439055",
            "isAnonymous": True,
            "language": "en",
            "jurisdiction": "NSW",
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
        }

    async def get_profile_for_export(self, owner):
        return self.profile

    async def get_consent_history_for_export(self, owner):
        return self.consent_history

    async def get_owner_documents(self, collection_key: str, owner, sort=None):
        return []

    async def get_audit_logs_for_owner(self, owner):
        return []

    async def get_conversation_children(self, session_ids, collection_key: str):
        return []


@pytest.fixture
def fake_privacy_repo(monkeypatch):
    repository = FakePrivacyRepository()

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(privacy_service_module, "get_privacy_repository", lambda: repository)
    monkeypatch.setattr(privacy_service_module, "create_audit_log", noop_audit)
    yield repository


@pytest.fixture
def fake_session(monkeypatch):
    async def fake_get_session_by_token(_token: str):
        class Session:
            id = "507f1f77bcf86cd799439055"
            user_id = None

        return Session()

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_create_privacy_request(fake_privacy_repo, fake_session):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/privacy-requests",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "requestType": "data_export",
                "confirmation": True,
            },
        )
    assert response.status_code == 201
    assert response.json()["data"]["request"]["requestType"] == "data_export"


def test_list_and_get_privacy_requests(fake_privacy_repo, fake_session):
    with TestClient(app) as client:
        create = client.post(
            "/api/v1/privacy-requests",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "requestType": "data_export",
                "confirmation": True,
            },
        )
        request_id = create.json()["data"]["request"]["_id"]
        listed = client.get(
            "/api/v1/privacy-requests/me",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        fetched = client.get(
            f"/api/v1/privacy-requests/{request_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["data"]["request"]["_id"] == request_id


def test_privacy_export_and_delete_request(fake_privacy_repo, fake_session):
    with TestClient(app) as client:
        export_response = client.get(
            "/api/v1/privacy/export",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        delete_response = client.post(
            "/api/v1/privacy/delete-request",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"confirmation": True},
        )
    assert export_response.status_code == 200
    assert export_response.json()["data"]["export"]["owner"]["type"] == "anonymous_session"
    assert delete_response.status_code == 201
    assert delete_response.json()["data"]["request"]["requestType"] == "data_deletion"
