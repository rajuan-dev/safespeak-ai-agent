from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.support import service as support_service_module


def _now() -> datetime:
    return datetime.now(UTC)


class FakeSupportRepository:
    def __init__(self) -> None:
        self.services = {}
        self.profiles = {}
        self.referrals = {}
        self.advocate_requests = {}
        self.help_requests = {}
        self.safety_plans = {}
        self.report_id = "507f1f77bcf86cd799439071"
        self.reports = {
            self.report_id: {
                "_id": ObjectId(self.report_id),
                "sessionId": ObjectId("507f1f77bcf86cd799439099"),
            }
        }

    async def seed_support_service(self, payload):
        self.services.setdefault(
            payload["key"],
            {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload},
        )

    async def seed_advocate_profile(self, payload):
        self.profiles.setdefault(
            payload["key"],
            {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload},
        )

    async def list_support_services(self, query):
        items = list(self.services.values())
        if query.get("isPublished") is True:
            items = [item for item in items if item.get("isPublished") and item.get("isActive")]
        if query.get("type"):
            items = [item for item in items if item.get("type") == query["type"]]
        return sorted(items, key=lambda item: (item.get("sortOrder", 0), item.get("name", "")))

    async def find_support_service(self, query):
        for item in self.services.values():
            if not item.get("isPublished") or not item.get("isActive"):
                continue
            for selector in query.get("$or", []):
                if "key" in selector and item.get("key") == selector["key"]:
                    return item
                if "name" in selector and item.get("name") == selector["name"]:
                    return item
                if "_id" in selector and item.get("_id") == selector["_id"]:
                    return item
        return None

    async def list_advocate_profiles(self, query):
        items = list(self.profiles.values())
        result = []
        for item in items:
            if item.get("isPublished") != query.get("isPublished"):
                continue
            if item.get("isActive") != query.get("isActive"):
                continue
            if item.get("optInStatus") != query.get("optInStatus"):
                continue
            if item.get("vetting", {}).get("status") != query.get("vetting.status"):
                continue
            result.append(item)
        return result

    async def find_advocate_profile(self, query):
        for item in await self.list_advocate_profiles(query):
            if query.get("key") and item.get("key") == query["key"]:
                return item
            if query.get("_id") and item.get("_id") == query["_id"]:
                return item
        return None

    async def find_duplicate_advocate_request(self, owner, advocate_profile_id, statuses):
        for request in self.advocate_requests.values():
            if (
                request.get("advocateProfileId") == advocate_profile_id
                and request.get("status") in statuses
            ):
                return request
        return None

    async def create_warm_referral(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.referrals[str(record["_id"])] = record
        return record

    async def create_advocate_request(self, payload):
        record = {"createdAt": _now(), "updatedAt": _now(), **payload}
        self.advocate_requests[str(record["_id"])] = record
        return record

    async def list_owned_advocate_requests(self, owner, query, limit):
        items = list(self.advocate_requests.values())
        if "status" in query:
            status_filter = query["status"]
            if isinstance(status_filter, dict):
                items = [item for item in items if item.get("status") in status_filter["$in"]]
            else:
                items = [item for item in items if item.get("status") == status_filter]
        return items[:limit]

    async def find_owned_advocate_request(self, owner, request_id):
        return self.advocate_requests.get(request_id)

    async def update_owned_advocate_request(self, owner, request_id, updates):
        record = self.advocate_requests.get(request_id)
        if not record:
            return None
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def create_help_support_request(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.help_requests[str(record["_id"])] = record
        return record

    async def list_safety_plans(self, owner):
        return list(self.safety_plans.values())[::-1]

    async def create_safety_plan(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.safety_plans[str(record["_id"])] = record
        return record

    async def update_safety_plan(self, owner, safety_plan_id, updates):
        record = self.safety_plans.get(safety_plan_id)
        if not record:
            return None
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def find_report_for_owner(self, owner, report_id):
        return self.reports.get(report_id)


@pytest.fixture
def fake_support_repo(monkeypatch):
    repository = FakeSupportRepository()

    async def noop_audit(*args, **kwargs):
        return None

    async def fake_consent(owner):
        return {
            "warm_referral": True,
            "advocate_request": True,
            "process_with_ai": False,
            "cloud_sync": True,
            "share_with_agencies": False,
        }

    monkeypatch.setattr(support_service_module, "get_support_repository", lambda: repository)
    monkeypatch.setattr(support_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(support_service_module, "get_current_consent", fake_consent)
    return repository


@pytest.fixture
def fake_support_no_consent(monkeypatch):
    async def fake_consent(owner):
        return {
            "warm_referral": False,
            "advocate_request": False,
            "process_with_ai": False,
            "cloud_sync": True,
            "share_with_agencies": False,
        }

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(support_service_module, "get_current_consent", fake_consent)
    monkeypatch.setattr(support_service_module, "create_audit_log", noop_audit)


@pytest.fixture
def fake_session(monkeypatch):
    async def fake_get_session_by_token(_token: str):
        return SimpleNamespace(id="507f1f77bcf86cd799439099", user_id=None)

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_support_services_and_recommendations(fake_support_repo, fake_session):
    with TestClient(app) as client:
        services = client.get(
            "/api/v1/support/services",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        service_id = services.json()["data"]["services"][0]["id"]
        fetched = client.get(
            f"/api/v1/support/services/{service_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        recommendations = client.post(
            "/api/v1/support/recommendations",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "needs": ["legal_information"],
                "reportId": fake_support_repo.report_id,
                "language": "en",
            },
        )
    assert services.status_code == 200
    assert fetched.status_code == 200
    assert recommendations.status_code == 200
    assert len(services.json()["data"]["services"]) >= 1
    assert recommendations.json()["data"]["recommendations"][0]["type"] == "legal_information"


def test_support_advocates_requests_and_cancel(fake_support_repo, fake_session):
    advocate = {
        "key": "general_support",
        "displayName": "General support advocate",
        "publicBio": "Bio",
        "languages": ["en"],
        "regions": ["national"],
        "issueTypes": ["general_support"],
        "culturalProfiles": [],
        "faithProfiles": [],
        "availability": "request_based",
        "isActive": True,
        "isPublished": True,
        "optInStatus": "opted_in",
        "vetting": {"status": "approved"},
    }
    fake_support_repo.profiles["general_support"] = {"_id": ObjectId(), **advocate}
    with TestClient(app) as client:
        advocates = client.get(
            "/api/v1/support/advocates",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        created = client.post(
            "/api/v1/support/advocate-request",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"advocateType": "general_support", "language": "en"},
        )
        request_id = created.json()["data"]["request"]["_id"]
        listed = client.get(
            "/api/v1/support/advocate-requests/me",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        fetched = client.get(
            f"/api/v1/support/advocate-requests/{request_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        cancelled = client.patch(
            f"/api/v1/support/advocate-requests/{request_id}/cancel",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"reasonCode": "user_cancelled"},
        )
    assert advocates.status_code == 200
    assert created.status_code == 201
    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["request"]["status"] == "cancelled"


def test_support_warm_referral_help_request_and_safety_plan(fake_support_repo, fake_session):
    with TestClient(app) as client:
        referral = client.post(
            "/api/v1/support/warm-referral",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "serviceId": "legal-aid",
                "contactPreference": "email",
                "safeContact": "person@example.com",
                "minimalSummary": {"incidentSummary": "Summary"},
            },
        )
        help_request = client.post(
            "/api/v1/support/help-request",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"title": "Need support", "message": "Please help"},
        )
        created_plan = client.post(
            "/api/v1/support/safety-plans",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"title": "My plan", "safePlaces": ["Library"], "emergencySteps": ["Call 000"]},
        )
        plan_id = created_plan.json()["data"]["safetyPlan"]["_id"]
        updated_plan = client.patch(
            f"/api/v1/support/safety-plans/{plan_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"title": "Updated plan", "warningSigns": ["Escalation"]},
        )
        listed_plans = client.get(
            "/api/v1/support/safety-plans",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert referral.status_code == 201
    assert help_request.status_code == 201
    assert created_plan.status_code == 201
    assert updated_plan.status_code == 200
    assert listed_plans.status_code == 200
    assert updated_plan.json()["data"]["safetyPlan"]["title"] == "Updated plan"


def test_support_consent_validation(fake_support_repo, fake_support_no_consent, fake_session):
    with TestClient(app) as client:
        referral = client.post(
            "/api/v1/support/warm-referral",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "serviceId": "legal-aid",
                "contactPreference": "email",
                "safeContact": "person@example.com",
            },
        )
        advocate_request = client.post(
            "/api/v1/support/advocate-request",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"advocateType": "general_support", "language": "en"},
        )
    assert referral.status_code == 403
    assert advocate_request.status_code == 403


def test_support_requires_session_or_user():
    with TestClient(app) as client:
        response = client.get("/api/v1/support/services")
    assert response.status_code == 401
