from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.profiles import service as profiles_service_module


class FakeProfilesRepository:
    def __init__(self) -> None:
        self.profile = None

    async def find_one(self, owner_filter):
        return self.profile

    async def upsert_one(self, owner_filter, payload):
        self.profile = {
            "_id": "507f1f77bcf86cd799439081",
            **owner_filter,
            **payload,
        }
        return self.profile

    async def list_active_language_taxonomies(self):
        return [{"key": "en", "label": "English"}]

    async def list_active_culture_taxonomies(self):
        return [{"label": "African", "metadata": {"profileGroup": "cultural"}}]

    async def list_managed_profiles(self, community_type: str):
        return [{"name": f"{community_type.title()} Profile"}]


@pytest.fixture
def fake_profiles_repo(monkeypatch):
    repository = FakeProfilesRepository()

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        profiles_service_module, "get_profiles_repository", lambda: repository
    )
    monkeypatch.setattr(profiles_service_module, "create_audit_log", noop_audit)
    yield repository


@pytest.fixture
def fake_anonymous_session(monkeypatch):
    async def fake_get_session_by_token(_token: str):
        return SimpleNamespace(
            id="507f1f77bcf86cd799439055",
            user_id=None,
            actor_type="anonymous_session",
        )

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_get_profile_defaults_with_anonymous_session(fake_profiles_repo, fake_anonymous_session):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/profile",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["profile"]["preferredLanguage"] == "en"


def test_update_profile_success(fake_profiles_repo, fake_anonymous_session):
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/profile",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "preferredLanguage": "ar",
                "jurisdiction": "VIC",
                "referralSharingPreference": True,
            },
        )
    assert response.status_code == 200
    assert response.json()["data"]["profile"]["preferredLanguage"] == "ar"
    assert response.json()["data"]["profile"]["jurisdiction"] == "VIC"


def test_get_profile_requires_session_or_user(fake_profiles_repo):
    with TestClient(app) as client:
        response = client.get("/api/v1/profile")
    assert response.status_code == 401
