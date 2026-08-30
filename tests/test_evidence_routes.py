import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import dependencies as auth_dependencies_module
from app.modules.evidence import service as evidence_service_module


def _now() -> datetime:
    return datetime.now(UTC)


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.report_id = "507f1f77bcf86cd799439111"
        self.evidence_id = "507f1f77bcf86cd799439122"
        self.report = {
            "_id": ObjectId(self.report_id),
            "status": "draft",
            "structuredFields": {},
            "deletedAt": None,
        }
        self.evidence_records = {}
        self.audit_chain = []

    async def create_evidence(self, payload):
        record = {
            "_id": ObjectId(self.evidence_id),
            "createdAt": _now(),
            "updatedAt": _now(),
            **payload,
        }
        if isinstance(record.get("reportId"), str):
            record["reportId"] = ObjectId(record["reportId"])
        self.evidence_records[self.evidence_id] = record
        return record

    async def find_evidence_for_owner(self, evidence_id: str, owner):
        return self.evidence_records.get(evidence_id)

    async def update_evidence(self, evidence_id: str, owner, updates):
        record = self.evidence_records.get(evidence_id)
        if not record:
            return None
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def list_evidence_for_report(self, report_id: str, owner):
        return list(self.evidence_records.values())

    async def find_report_for_owner(self, report_id: str, owner):
        return self.report if report_id == self.report_id else None

    async def update_report(self, report_id: str, updates):
        self.report.update(updates)
        return self.report

    async def latest_audit_record(self, evidence_id: str):
        return self.audit_chain[-1] if self.audit_chain else None

    async def create_audit_record(self, payload):
        record = {**payload, "_id": ObjectId(), "createdAt": payload.get("createdAt") or _now()}
        self.audit_chain.append(record)
        return record

    async def list_audit_chain(self, evidence_id: str):
        return list(self.audit_chain)


@pytest.fixture
def fake_evidence_repo(tmp_path, monkeypatch):
    repository = FakeEvidenceRepository()

    async def fake_consent(owner):
        return {
            "cloud_sync": True,
            "process_with_ai": True,
            "transcribe_audio": True,
        }

    async def noop_audit(*args, **kwargs):
        return None

    async def fake_transcribe(path: str, language: str | None = None):
        return {
            "text": "Transcript text",
            "language": language or "en",
            "model": "gpt-4o-transcribe",
            "provider": "openai",
            "confidence": 0.99,
        }

    monkeypatch.setattr(evidence_service_module, "get_evidence_repository", lambda: repository)
    monkeypatch.setattr(evidence_service_module, "get_current_consent", fake_consent)
    monkeypatch.setattr(evidence_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(evidence_service_module, "transcribe_audio_file", fake_transcribe)
    monkeypatch.setattr(
        evidence_service_module,
        "get_settings",
        lambda: SimpleNamespace(
            EVIDENCE_MAX_FILE_SIZE_BYTES=1_048_576,
            EVIDENCE_LOCAL_STORAGE_PATH=Path(tmp_path),
            EVIDENCE_S3_BUCKET=None,
            EVIDENCE_S3_PREFIX="evidence-vault",
            EVIDENCE_AUDIT_SIGNING_KEY="audit-key",
            EVIDENCE_ENCRYPTION_KEY="encryption-key",
            AWS_REGION="us-east-1",
        ),
    )
    return repository


@pytest.fixture
def fake_session(monkeypatch):
    async def fake_get_session_by_token(_token: str):
        class Session:
            id = "507f1f77bcf86cd799439199"
            user_id = None

        return Session()

    monkeypatch.setattr(auth_dependencies_module, "get_session_by_token", fake_get_session_by_token)


def test_evidence_upload_verify_and_delete(fake_evidence_repo, fake_session):
    payload = b"voice evidence"
    sha256_hash = hashlib.sha256(payload).hexdigest()
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/evidence/upload-url",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "reportId": fake_evidence_repo.report_id,
                "type": "audio",
                "fileName": "note.wav",
                "mimeType": "audio/wav",
                "size": len(payload),
            },
        )
        complete = client.post(
            "/api/v1/evidence/complete-upload",
            headers={"X-SafeSpeak-Session": "anon-token"},
            files={"file": ("note.wav", payload, "audio/wav")},
            data={
                "evidenceId": fake_evidence_repo.evidence_id,
                "sha256Hash": sha256_hash,
                "metadata": json.dumps({"source": "mobile"}),
            },
        )
        listed = client.get(
            f"/api/v1/reports/{fake_evidence_repo.report_id}/evidence",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        fetched = client.get(
            f"/api/v1/evidence/{fake_evidence_repo.evidence_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        metadata = client.get(
            f"/api/v1/evidence/{fake_evidence_repo.evidence_id}/metadata",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        verified = client.post(
            f"/api/v1/evidence/{fake_evidence_repo.evidence_id}/verify-hash",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={"sha256Hash": sha256_hash},
        )
        deleted = client.delete(
            f"/api/v1/evidence/{fake_evidence_repo.evidence_id}",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert created.status_code == 201
    assert complete.status_code == 200
    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert metadata.status_code == 200
    assert verified.status_code == 200
    assert verified.json()["data"]["verification"]["verified"] is True
    assert deleted.status_code == 200


def test_evidence_audit_chain_and_transcription(fake_evidence_repo, fake_session):
    payload = b"voice evidence"
    sha256_hash = hashlib.sha256(payload).hexdigest()
    with TestClient(app) as client:
        client.post(
            "/api/v1/evidence/upload-url",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "reportId": fake_evidence_repo.report_id,
                "type": "audio",
                "fileName": "note.wav",
                "mimeType": "audio/wav",
                "size": len(payload),
            },
        )
        client.post(
            "/api/v1/evidence/complete-upload",
            headers={"X-SafeSpeak-Session": "anon-token"},
            files={"file": ("note.wav", payload, "audio/wav")},
            data={"evidenceId": fake_evidence_repo.evidence_id, "sha256Hash": sha256_hash},
        )
        transcribed = client.post(
            f"/api/v1/evidence/{fake_evidence_repo.evidence_id}/transcribe",
            headers={"X-SafeSpeak-Session": "anon-token"},
            json={
                "reportId": fake_evidence_repo.report_id,
                "saveTranscript": True,
                "useAsNarrative": True,
            },
        )
        transcription = client.get(
            f"/api/v1/evidence/{fake_evidence_repo.evidence_id}/transcription",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
        audit_chain = client.get(
            f"/api/v1/evidence/{fake_evidence_repo.evidence_id}/audit-chain",
            headers={"X-SafeSpeak-Session": "anon-token"},
        )
    assert transcribed.status_code == 200
    assert transcription.status_code == 200
    assert audit_chain.status_code == 200
    assert len(audit_chain.json()["data"]["auditChain"]) >= 3
    assert fake_evidence_repo.report["originalNarrative"] == "Transcript text"


def test_evidence_requires_authentication(fake_evidence_repo):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/evidence/upload-url",
            json={
                "reportId": fake_evidence_repo.report_id,
                "type": "audio",
                "fileName": "note.wav",
                "mimeType": "audio/wav",
                "size": 1,
            },
        )
    assert response.status_code == 401
