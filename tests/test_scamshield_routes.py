from datetime import UTC, datetime

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.scamshield import service as scamshield_service_module


def _now() -> datetime:
    return datetime.now(UTC)


class FakeScamShieldRepository:
    def __init__(self) -> None:
        self.analysis_id = "507f1f77bcf86cd799439061"
        self.report_id = "507f1f77bcf86cd799439062"
        self.analyses: dict[str, dict] = {}
        self.reports: dict[str, dict] = {}

    async def create_analysis(self, payload):
        analysis_id = payload.get("_id") or ObjectId(self.analysis_id)
        record = {"_id": analysis_id, "createdAt": _now(), "updatedAt": _now(), **payload}
        self.analyses[str(record["_id"])] = record
        return record

    async def find_analysis_for_owner(self, analysis_id: str, owner):
        return self.analyses.get(analysis_id)

    async def update_analysis(self, analysis_id: str, owner, updates):
        record = self.analyses.get(analysis_id)
        if not record:
            return None
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def create_report(self, payload):
        report = {
            "_id": ObjectId(self.report_id),
            "createdAt": _now(),
            "updatedAt": _now(),
            **payload,
        }
        self.reports[str(report["_id"])] = report
        return report

    async def find_report_for_owner(self, report_id, owner):
        return self.reports.get(report_id)

    async def find_evidence_for_owner(self, evidence_id, owner):
        return None


@pytest.fixture
def fake_scamshield_repo(monkeypatch):
    repository = FakeScamShieldRepository()

    monkeypatch.setattr(scamshield_service_module, "get_scamshield_repository", lambda: repository)
    return repository


@pytest.fixture
def fake_server_consent(monkeypatch):
    async def fake_consent(owner):
        return {
            "process_with_ai": True,
            "cloud_sync": True,
            "share_with_agencies": True,
            "anonymised_analytics": False,
        }

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(scamshield_service_module, "get_current_consent", fake_consent)
    monkeypatch.setattr(scamshield_service_module, "create_audit_log", noop_audit)


@pytest.fixture
def fake_local_only_consent(monkeypatch):
    async def fake_consent(owner):
        return {
            "process_with_ai": True,
            "cloud_sync": False,
            "share_with_agencies": False,
            "anonymised_analytics": False,
        }

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(scamshield_service_module, "get_current_consent", fake_consent)
    monkeypatch.setattr(scamshield_service_module, "create_audit_log", noop_audit)


@pytest.fixture
def fake_session(monkeypatch):
    async def fake_get_session_by_token(_token: str):
        class Session:
            id = "507f1f77bcf86cd799439099"
            user_id = None

        return Session()

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_scamshield_text_and_lookup(fake_scamshield_repo, fake_server_consent, fake_session):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/scamshield/analyze-text",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"text": "Urgent bank message asking for OTP and payment now", "language": "en"},
        )
        analysis_id = created.json()["data"]["analysis"]["_id"]
        fetched = client.get(
            f"/api/v1/scamshield/{analysis_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert created.status_code == 201
    assert fetched.status_code == 200
    assert created.json()["message"] == "ScamShield text analysis completed"
    assert fetched.json()["data"]["analysis"]["riskLevel"] in {"medium", "high", "critical"}


def test_scamshield_email_url_redact_and_draft(
    fake_scamshield_repo, fake_server_consent, fake_session
):
    with TestClient(app) as client:
        email_response = client.post(
            "/api/v1/scamshield/analyze-email",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "subject": "Final notice",
                "from": "support@fake-bank.example",
                "body": (
                    "Pay now or your account is closed. Use OTP 123456 and click "
                    "https://bad-example.zip"
                ),
                "headers": {
                    "reply-to": "fraud@bad-example.zip",
                    "Authentication-Results": "spf fail dkim fail",
                },
            },
        )
        analysis_id = email_response.json()["data"]["analysis"]["_id"]
        url_response = client.post(
            "/api/v1/scamshield/check-url",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"url": "https://secure-login-account-update.zip"},
        )
        redact_response = client.post(
            "/api/v1/scamshield/redact",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "text": "Email me at person@example.com or call +61 400 123 999",
                "replacement": "labels",
            },
        )
        draft_response = client.post(
            f"/api/v1/scamshield/{analysis_id}/generate-report-draft",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"notes": "User wants a draft", "autoRedactPII": True},
        )
    assert email_response.status_code == 201
    assert url_response.status_code == 201
    assert redact_response.status_code == 200
    assert draft_response.status_code == 200
    assert "[EMAIL]" in redact_response.json()["data"]["result"]["redactedText"]
    assert draft_response.json()["data"]["analysis"]["draftReport"]["informationOnly"] is True


def test_scamshield_submit_by_snapshot_and_by_id(
    fake_scamshield_repo, fake_server_consent, fake_session
):
    with TestClient(app) as client:
        local_submit = client.post(
            "/api/v1/scamshield/submit",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "analysisSnapshot": {
                    "type": "text",
                    "riskLevel": "high",
                    "riskScore": 77,
                    "summary": "Likely phishing attempt",
                    "indicators": ["urgent pressure"],
                    "redFlags": ["Detected urgent pressure."],
                    "recommendations": ["Do not send money."],
                    "metadata": {"language": "en"},
                },
                "destination": "SafeSpeak review queue",
                "consentToShare": True,
            },
        )
        created = client.post(
            "/api/v1/scamshield/analyze-text",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"text": "Urgent scam text with link https://fake.top"},
        )
        analysis_id = created.json()["data"]["analysis"]["_id"]
        by_id_submit = client.post(
            f"/api/v1/scamshield/{analysis_id}/submit",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"destination": "SafeSpeak review queue", "consentToShare": True},
        )
    assert local_submit.status_code == 200
    assert by_id_submit.status_code == 200
    assert local_submit.json()["data"]["analysis"]["status"] == "submitted"
    assert by_id_submit.json()["data"]["analysis"]["metadata"]["linkedReportId"]


def test_scamshield_local_only_analysis(
    fake_local_only_consent, fake_scamshield_repo, fake_session
):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/scamshield/analyze-text",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"text": "Just checking this odd message", "language": "en"},
        )
    assert response.status_code == 201
    assert response.json()["data"]["analysis"]["metadata"]["storageMode"] == "local_only"
    assert "_id" not in response.json()["data"]["analysis"]


def test_scamshield_requires_session_when_missing():
    with TestClient(app) as client:
        response = client.post("/api/v1/scamshield/analyze-text", json={"text": "hello"})
    assert response.status_code == 401
