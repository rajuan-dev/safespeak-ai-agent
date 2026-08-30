from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import service as auth_service_module
from app.modules.auth.model import AuthenticatedUserPayload
from app.modules.auth.repository import get_auth_repository
from app.modules.auth.security import build_auth_tokens, hash_password


class FakeUsersAuthRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.users = {
            "507f1f77bcf86cd799439011": {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "passwordHash": hash_password("StrongPassword1"),
                "fullName": "Test User",
                "contactNo": None,
                "role": "public_user",
                "status": "active",
                "authProvider": "local",
                "isEmailVerified": True,
                "createdAt": now,
                "updatedAt": now,
            }
        }

    async def find_user_by_id(self, user_id: str):
        return self.users.get(user_id)

    async def find_user_by_email(self, email: str):
        for user in self.users.values():
            if user["email"] == email:
                return user
        return None

    async def update_user(self, user_id: str, updates):
        user = self.users[user_id]
        user.update(updates)
        user["updatedAt"] = datetime.now(UTC)
        return user


@pytest.fixture
def fake_auth_repo(monkeypatch):
    repository = FakeUsersAuthRepository()

    async def noop_audit(*args, **kwargs):
        return None

    app.dependency_overrides[get_auth_repository] = lambda: repository
    monkeypatch.setattr(auth_service_module, "get_auth_repository", lambda: repository)
    monkeypatch.setattr(auth_service_module, "create_audit_log", noop_audit)
    try:
        yield repository
    finally:
        app.dependency_overrides.clear()


def make_access_token(user_id: str, role: str = "public_user") -> str:
    return build_auth_tokens(
        AuthenticatedUserPayload(userId=user_id, role=role)
    ).access_token


def test_get_current_user_success(fake_auth_repo):
    token = make_access_token("507f1f77bcf86cd799439011")
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "user@example.com"


def test_update_current_user_success(fake_auth_repo):
    token = make_access_token("507f1f77bcf86cd799439011")
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "fullName": "Updated User",
                "email": "updated@example.com",
                "contactNo": "+61 400 000 000",
            },
        )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["fullName"] == "Updated User"
    assert response.json()["data"]["user"]["email"] == "updated@example.com"


def test_get_current_user_unauthorized(fake_auth_repo):
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
