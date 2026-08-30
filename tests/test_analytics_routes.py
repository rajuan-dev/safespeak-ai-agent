import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.modules.analytics import service as analytics_service_module
from app.modules.auth.model import AuthenticatedUserPayload
from app.modules.auth.repository import get_auth_repository
from app.modules.auth.security import build_auth_tokens


def _now() -> datetime:
    return datetime.now(UTC)


class FakeAuthRepository:
    def __init__(self) -> None:
        now = _now()
        self.users = {
            "507f1f77bcf86cd799439012": {
                "_id": "507f1f77bcf86cd799439012",
                "email": "admin@example.com",
                "fullName": "Admin User",
                "role": "super_admin",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439015": {
                "_id": "507f1f77bcf86cd799439015",
                "email": "analytics@example.com",
                "fullName": "Analytics User",
                "role": "analytics_viewer",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439011": {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "fullName": "User",
                "role": "public_user",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
        }

    async def find_user_by_id(self, user_id: str):
        return self.users.get(user_id)


class FakeAnalyticsRepository:
    def __init__(self) -> None:
        now = _now()
        self.reports = []
        for offset in range(6):
            self.reports.append(
                {
                    "status": "submitted" if offset < 5 else "draft",
                    "severity": "high" if offset < 5 else "low",
                    "incidentType": "harassment",
                    "language": "en",
                    "jurisdiction": "NSW",
                    "location": {"lga": "Sydney"},
                    "createdAt": now - timedelta(days=offset),
                    "deletedAt": None,
                    "consentSnapshot": {"use_anonymised_analytics": True},
                }
            )

    async def list_reports(self, match):
        rows = []
        for report in self.reports:
            if report["consentSnapshot"]["use_anonymised_analytics"] != match["consentSnapshot.use_anonymised_analytics"]:
                continue
            if match.get("jurisdiction") and report.get("jurisdiction") != match["jurisdiction"]:
                continue
            if match.get("language") and report.get("language") != match["language"]:
                continue
            rows.append(report)
        return rows


def make_token(user_id: str, role: str) -> str:
    return build_auth_tokens(AuthenticatedUserPayload(userId=user_id, role=role)).access_token


@pytest.fixture
def analytics_fakes(monkeypatch):
    auth_repo = FakeAuthRepository()
    analytics_repo = FakeAnalyticsRepository()
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    monkeypatch.setattr(analytics_service_module, "get_analytics_repository", lambda: analytics_repo)
    try:
        yield analytics_repo
    finally:
        app.dependency_overrides.clear()


def test_analytics_overview_and_export(analytics_fakes):
    token = make_token("507f1f77bcf86cd799439015", "analytics_viewer")
    with TestClient(app) as client:
        overview = client.get("/api/v1/admin/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        heatmap = client.get("/api/v1/admin/analytics/heatmap", headers={"Authorization": f"Bearer {token}"})
        trends = client.get("/api/v1/admin/analytics/trends", headers={"Authorization": f"Bearer {token}"})
        categories = client.get("/api/v1/admin/analytics/categories", headers={"Authorization": f"Bearer {token}"})
        languages = client.get("/api/v1/admin/analytics/languages", headers={"Authorization": f"Bearer {token}"})
        export = client.get("/api/v1/admin/analytics/export", headers={"Authorization": f"Bearer {token}"})
    assert overview.status_code == 200
    assert overview.json()["data"]["overview"]["totalReports"] == 6
    assert heatmap.status_code == 200
    assert trends.status_code == 200
    assert categories.status_code == 200
    assert languages.status_code == 200
    assert export.status_code == 200
    assert export.json()["data"]["export"]["privacy"]["rawReportsExposed"] is False


def test_analytics_rbac_and_public_route(analytics_fakes):
    token = make_token("507f1f77bcf86cd799439011", "public_user")
    with TestClient(app) as client:
        forbidden = client.get("/api/v1/admin/analytics/overview", headers={"Authorization": f"Bearer {token}"})
        public_route = client.get("/api/v1/analytics/public/local-intelligence")
    assert forbidden.status_code == 403
    assert public_route.status_code == 200
    assert public_route.json()["data"]["intelligence"]["privacy"]["anonymisedOnly"] is True
