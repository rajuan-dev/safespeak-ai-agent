from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.reports import service as reports_service_module


def _now() -> datetime:
    return datetime.now(UTC)


class FakeReportsRepository:
    def __init__(self) -> None:
        self.report_id = "507f1f77bcf86cd799439011"
        self.destination_id = "507f1f77bcf86cd799439022"
        self.submission_id = "507f1f77bcf86cd799439033"
        self.reports = {}
        self.submissions = {}
        self.destination = {
            "_id": ObjectId(self.destination_id),
            "name": "NSW Support Desk",
            "key": "nsw_support",
            "type": "agency",
            "channel": "manual_export_json",
            "jurisdiction": "NSW",
            "languages": ["en"],
            "metadata": {"requiredConsentFlags": ["share_with_agencies"]},
            "isActive": True,
        }

    async def create_report(self, payload):
        record = {
            "_id": ObjectId(self.report_id),
            "createdAt": _now(),
            "updatedAt": _now(),
            **payload,
        }
        self.reports[self.report_id] = record
        return record

    async def list_reports(self, owner):
        return list(self.reports.values())[::-1]

    async def find_report_for_owner(self, report_id: str, owner):
        return self.reports.get(report_id)

    async def update_report(self, report_id: str, owner, updates):
        record = self.reports.get(report_id)
        if not record:
            return None
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def append_report_history(self, report_id: str, owner, history_entry, extra_updates=None):
        record = self.reports.get(report_id)
        if not record:
            return None
        record.setdefault("statusHistory", []).append(history_entry)
        if extra_updates:
            record.update(extra_updates)
        record["updatedAt"] = _now()
        return record

    async def create_submission(self, payload):
        record = {
            "_id": ObjectId(self.submission_id),
            "createdAt": _now(),
            "updatedAt": _now(),
            **payload,
        }
        self.submissions[self.submission_id] = record
        return record

    async def list_submissions_for_report(self, report_id: str, owner):
        return list(self.submissions.values())[::-1]

    async def find_submission_by_destination(self, report_id: str, owner, destination_id: str):
        for record in self.submissions.values():
            if record.get("destinationId") == destination_id:
                return record
        return None

    async def find_submission_for_owner(self, submission_id: str, report_id: str, owner):
        return self.submissions.get(submission_id)

    async def update_submission(self, submission_id: str, report_id: str, owner, updates):
        record = self.submissions.get(submission_id)
        if not record:
            return None
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def get_profile(self, owner):
        return {"preferredLanguage": "en", "jurisdiction": "NSW"}

    async def get_anonymous_session(self, session_id):
        return {
            "_id": ObjectId("507f1f77bcf86cd799439099"),
            "language": "en",
            "jurisdiction": "NSW",
        }

    async def count_evidence_for_report(self, report_id: str, owner):
        return 1

    async def list_evidence_for_report(self, report_id: str, owner):
        return [
            {
                "_id": ObjectId("507f1f77bcf86cd799439044"),
                "type": "audio",
                "fileName": "voice-note.wav",
                "mimeType": "audio/wav",
                "size": 128,
            }
        ]

    async def get_destinations(self, jurisdiction: str, incident_type=None):
        return [self.destination]

    async def get_destination(self, destination_id: str):
        if destination_id == self.destination_id:
            return self.destination
        return None

    async def get_template_for_destination(self, destination_id: str):
        return {
            "_id": ObjectId("507f1f77bcf86cd799439055"),
            "destinationId": ObjectId(destination_id),
            "isActive": True,
        }

    async def get_conversation_bundle(self, conversation_session_id: str, owner):
        return {
            "session": {"language": "en", "jurisdiction": "NSW"},
            "messages": [{"content": "I need to report what happened."}],
            "facts": [{"category": "incident", "value": "abuse"}],
            "triage": {"incidentType": "abuse", "severity": "high"},
        }


@pytest.fixture
def fake_reports_repo(tmp_path, monkeypatch):
    repository = FakeReportsRepository()

    async def fake_consent(owner):
        return {
            "cloud_sync": True,
            "share_with_agencies": True,
            "anonymised_analytics": False,
        }

    async def noop_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(reports_service_module, "get_reports_repository", lambda: repository)
    monkeypatch.setattr(reports_service_module, "get_current_consent", fake_consent)
    monkeypatch.setattr(reports_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(
        reports_service_module,
        "get_settings",
        lambda: SimpleNamespace(REPORT_DELIVERY_EXPORT_PATH=Path(tmp_path)),
    )
    return repository


@pytest.fixture
def fake_session(monkeypatch):
    async def fake_get_session_by_token(_token: str):
        class Session:
            id = "507f1f77bcf86cd799439099"
            user_id = None

        return Session()

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_reports_crud_and_status_routes(fake_reports_repo, fake_session):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/reports",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "originalNarrative": "Narrative",
                "incidentType": "abuse",
                "severity": "high",
                "structuredFields": {"what": "Narrative"},
            },
        )
        report_id = created.json()["data"]["report"]["_id"]
        listed = client.get("/api/v1/reports", headers={"X-SafeSpeak-Session": "anon-token"})
        fetched = client.get(
            f"/api/v1/reports/{report_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        updated = client.patch(
            f"/api/v1/reports/{report_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"context": "Updated context"},
        )
        status_response = client.get(
            f"/api/v1/reports/{report_id}/status",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        deleted = client.delete(
            f"/api/v1/reports/{report_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert created.status_code == 201
    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert updated.status_code == 200
    assert status_response.status_code == 200
    assert deleted.status_code == 200
    assert status_response.json()["data"]["status"]["refNo"].startswith("SSR-")


def test_reports_info_only_withdraw_and_submission(fake_reports_repo, fake_session):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/reports",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "originalNarrative": "Narrative",
                "incidentType": "abuse",
                "severity": "high",
                "structuredFields": {"what": "Narrative"},
            },
        )
        report_id = created.json()["data"]["report"]["_id"]
        submission = client.post(
            f"/api/v1/reports/{report_id}/submissions",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "destinationId": fake_reports_repo.destination_id,
                "anonymityMode": "identified",
                "confirmConsent": True,
            },
        )
        submission_id = submission.json()["data"]["submission"]["_id"]
        acknowledged = client.post(
            f"/api/v1/reports/{report_id}/submissions/{submission_id}/acknowledge",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "status": "acknowledged",
                "externalReference": "EXT-1",
                "acknowledgementPayload": {"ok": True},
            },
        )
        info_only = client.post(
            f"/api/v1/reports/{report_id}/mark-info-only",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"reason": "statistics only"},
        )
        timeline = client.get(
            f"/api/v1/reports/{report_id}/timeline",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        destinations = client.get(
            f"/api/v1/reports/{report_id}/destinations",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        previews = client.post(
            f"/api/v1/reports/{report_id}/submission-previews",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "destinationIds": [fake_reports_repo.destination_id],
                "anonymityMode": "identified",
            },
        )
        submissions = client.get(
            f"/api/v1/reports/{report_id}/submissions",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        withdraw = client.post(
            f"/api/v1/reports/{report_id}/withdraw",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"reason": "user request"},
        )
    assert info_only.status_code == 200
    assert info_only.json()["data"]["report"]["originalNarrative"] is None
    assert timeline.status_code == 200
    assert destinations.status_code == 200
    assert previews.status_code == 200
    assert submission.status_code == 201
    assert acknowledged.status_code == 200
    assert submissions.status_code == 200
    assert withdraw.status_code == 200


def test_report_create_requires_authentication(fake_reports_repo):
    with TestClient(app) as client:
        response = client.post("/api/v1/reports", json={"originalNarrative": "Narrative"})
    assert response.status_code == 401
