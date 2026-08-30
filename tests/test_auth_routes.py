from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import router as auth_router_module
from app.modules.auth import service as auth_service_module
from app.modules.auth.model import AuthenticatedUserPayload
from app.modules.auth.repository import get_auth_repository
from app.modules.auth.security import build_auth_tokens


class FakeAuthRepository:
    def __init__(self):
        now = datetime.now(UTC)
        self.users = {
            "507f1f77bcf86cd799439011": {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "passwordHash": auth_service_module.hash_password("StrongPassword1"),
                "fullName": "Test User",
                "role": "public_user",
                "status": "active",
                "authProvider": "local",
                "isEmailVerified": False,
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439012": {
                "_id": "507f1f77bcf86cd799439012",
                "email": "admin@example.com",
                "passwordHash": auth_service_module.hash_password("AdminPassword1"),
                "fullName": "Admin User",
                "role": "super_admin",
                "status": "active",
                "authProvider": "local",
                "isEmailVerified": True,
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439013": {
                "_id": "507f1f77bcf86cd799439013",
                "email": "inactive@example.com",
                "passwordHash": auth_service_module.hash_password("InactivePassword1"),
                "fullName": "Inactive User",
                "role": "public_user",
                "status": "inactive",
                "authProvider": "local",
                "isEmailVerified": False,
                "createdAt": now,
                "updatedAt": now,
            },
        }
        self.reset_requests = {}

    async def find_user_by_email(self, email: str):
        for user in self.users.values():
            if user["email"] == email:
                return user
        return None

    async def find_user_by_google_or_email(self, google_id: str, email: str):
        for user in self.users.values():
            if user.get("googleId") == google_id or user["email"] == email:
                return user
        return None

    async def find_user_by_id(self, user_id: str):
        return self.users.get(user_id)

    async def create_user(self, payload):
        user_id = "507f1f77bcf86cd799439099"
        now = datetime.now(UTC)
        user = {"_id": user_id, "createdAt": now, "updatedAt": now, **payload}
        self.users[user_id] = user
        return user

    async def update_user(self, user_id: str, updates):
        user = self.users[user_id]
        user.update(updates)
        user["updatedAt"] = datetime.now(UTC)
        return user

    async def unset_refresh_token_hash(self, user_id: str):
        self.users[user_id].pop("refreshTokenHash", None)

    async def update_refresh_token_hash(self, user_id: str, refresh_token_hash: str):
        self.users[user_id]["refreshTokenHash"] = refresh_token_hash
        self.users[user_id]["lastLoginAt"] = datetime.now(UTC)
        self.users[user_id]["updatedAt"] = datetime.now(UTC)

    async def expire_active_reset_requests(self, user_id: str, audience: str):
        for request in self.reset_requests.values():
            if request["userId"] == user_id and request["audience"] == audience:
                request["expiresAt"] = datetime.now(UTC)

    async def create_password_reset_request(self, payload):
        request_id = "507f1f77bcf86cd799439088"
        now = datetime.now(UTC)
        record = {"_id": request_id, "createdAt": now, "updatedAt": now, **payload}
        if isinstance(record["userId"], str):
            record["userId"] = record["userId"]
        else:
            record["userId"] = str(record["userId"])
        self.reset_requests[request_id] = record
        return record

    async def find_password_reset_request(
        self, reset_request_id: str, email: str, audience: str
    ):
        request = self.reset_requests.get(reset_request_id)
        if request and request["email"] == email and request["audience"] == audience:
            return request
        return None

    async def update_password_reset_request(self, reset_request_id: str, updates):
        request = self.reset_requests[reset_request_id]
        request.update(updates)
        request["updatedAt"] = datetime.now(UTC)
        return request

    async def expire_other_password_reset_requests(
        self,
        user_id: str,
        audience: str,
        keep_request_id: str,
    ):
        for request_id, request in self.reset_requests.items():
            if (
                request["userId"] == user_id
                and request["audience"] == audience
                and request_id != keep_request_id
            ):
                request["expiresAt"] = datetime.now(UTC)


@pytest.fixture
def fake_repo(monkeypatch):
    repository = FakeAuthRepository()
    monkeypatch.setattr(auth_service_module, "get_auth_repository", lambda: repository)
    app.dependency_overrides[get_auth_repository] = lambda: repository

    async def noop_audit(*args, **kwargs):
        return None

    async def fake_delivery(**kwargs):
        return {"mode": "development_outbox", "reference": "memory://reset"}

    monkeypatch.setattr(auth_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(auth_service_module, "deliver_password_reset_otp", fake_delivery)
    try:
        yield repository
    finally:
        app.dependency_overrides.clear()


def make_access_token(user_id: str, role: str) -> str:
    return build_auth_tokens(AuthenticatedUserPayload(userId=user_id, role=role)).access_token


def test_register_success(fake_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "VeryStrongPass1",
                "fullName": "New User",
            },
        )
    assert response.status_code == 201
    assert response.json()["success"] is True


def test_register_duplicate_email(fake_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "VeryStrongPass1"},
        )
    assert response.status_code == 409
    assert response.json()["message"] == "Email is already registered"


def test_login_success(fake_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "StrongPassword1"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "user@example.com"


def test_login_wrong_password(fake_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "WrongPassword"},
        )
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"


def test_login_inactive_user(fake_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@example.com", "password": "InactivePassword1"},
        )
    assert response.status_code == 403
    assert response.json()["message"] == "User account is not active"


def test_refresh_valid_and_reused_refresh_token(fake_repo):
    with TestClient(app) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "StrongPassword1"},
        )
        refresh_token = login_response.json()["data"]["tokens"]["refreshToken"]

        first_refresh = client.post("/api/v1/auth/refresh", json={"refreshToken": refresh_token})
        second_refresh = client.post("/api/v1/auth/refresh", json={"refreshToken": refresh_token})

    assert first_refresh.status_code == 200
    assert second_refresh.status_code == 401
    assert second_refresh.json()["message"] == "Invalid refresh token"


def test_admin_login_success(fake_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/admin/login",
            json={"email": "admin@example.com", "password": "AdminPassword1"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["role"] == "super_admin"


def test_admin_login_forbidden_for_public_user(fake_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/admin/login",
            json={"email": "user@example.com", "password": "StrongPassword1"},
        )
    assert response.status_code == 403
    assert response.json()["message"] == "Admin access is required"


def test_me_requires_auth(fake_repo):
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_success(fake_repo):
    token = make_access_token("507f1f77bcf86cd799439011", "public_user")
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "user@example.com"


def test_change_password_success(fake_repo):
    token = make_access_token("507f1f77bcf86cd799439011", "public_user")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"currentPassword": "StrongPassword1", "newPassword": "ChangedPass1"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "user@example.com"


def test_forgot_password_and_reset_flow(fake_repo):
    with TestClient(app) as client:
        forgot = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "user@example.com", "audience": "public"},
        )
        request_id = forgot.json()["data"]["resetRequestId"]
        otp = forgot.json()["data"]["debugOtp"]
        verify = client.post(
            "/api/v1/auth/verify-reset-otp",
            json={
                "email": "user@example.com",
                "audience": "public",
                "resetRequestId": request_id,
                "otp": otp,
            },
        )
        reset = client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": "user@example.com",
                "audience": "public",
                "resetRequestId": request_id,
                "resetToken": verify.json()["data"]["resetToken"],
                "newPassword": "BrandNewPass1",
            },
        )
    assert forgot.status_code == 200
    assert verify.status_code == 200
    assert reset.status_code == 200


def test_logout_success(fake_repo):
    token = make_access_token("507f1f77bcf86cd799439011", "public_user")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200


def test_deactivate_success(fake_repo):
    token = make_access_token("507f1f77bcf86cd799439011", "public_user")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/deactivate",
            headers={"Authorization": f"Bearer {token}"},
            json={"confirmation": "DEACTIVATE"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["status"] == "inactive"


def test_google_login_redirect_when_configured(fake_repo, monkeypatch):
    monkeypatch.setattr(auth_router_module, "is_google_oauth_configured", lambda: True)
    monkeypatch.setattr(
        auth_router_module,
        "build_google_login_redirect_url",
        lambda: "https://accounts.google.com/mock",
    )
    with TestClient(app) as client:
        response = client.get("/api/auth/google", follow_redirects=False)
    assert response.status_code == 302


def test_google_callback_redirects_to_frontend(fake_repo, monkeypatch):
    monkeypatch.setattr(auth_router_module, "is_google_oauth_configured", lambda: True)

    async def fake_exchange(code: str):
        return {
            "googleId": "google-1",
            "email": "user@example.com",
            "fullName": "Test User",
            "avatarUrl": None,
        }

    async def fake_google_login(**kwargs):
        return {
            "user": {"id": "507f1f77bcf86cd799439011"},
            "tokens": {"accessToken": "a", "refreshToken": "b"},
        }

    monkeypatch.setattr(auth_router_module, "exchange_google_code_for_profile", fake_exchange)
    monkeypatch.setattr(auth_router_module, "login_with_google_profile", fake_google_login)
    monkeypatch.setattr(
        auth_router_module,
        "build_client_auth_callback_redirect",
        lambda auth_data: "https://frontend.example/auth/callback#auth=data",
    )

    with TestClient(app) as client:
        response = client.get("/api/auth/google/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://frontend.example/auth/callback#auth=data"
