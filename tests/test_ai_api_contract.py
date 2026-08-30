from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from fastapi.testclient import TestClient

from app.api.ai import router
from app.core.responses import failure
from app.core.security import (
    Principal,
    require_ai_consent,
    require_ai_or_transcription_consent,
)


def build_client() -> TestClient:
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return ORJSONResponse(
            failure(
                "Validation failed",
                error_code="VALIDATION_ERROR",
                request_id=getattr(request.state, "request_id", None),
                errors=exc.errors(),
            ),
            status_code=400,
        )

    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[require_ai_consent] = lambda: Principal(
        actor_type="user",
        user_id="507f1f77bcf86cd799439011",
    )
    app.dependency_overrides[require_ai_or_transcription_consent] = lambda: Principal(
        actor_type="user",
        user_id="507f1f77bcf86cd799439011",
    )
    return TestClient(app)


def test_triage_route_matches_backend_message_and_meta(monkeypatch):
    async def fake_triage(request, principal):
        return {"summary": "ok", "reviewStatus": "pending_human_review"}

    monkeypatch.setattr("app.api.ai.triage_report", fake_triage)
    client = build_client()

    response = client.post("/api/v1/ai/triage-report", json={"narrative": "test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Report triaged"
    assert payload["meta"] == {"informationOnly": True}
    assert payload["data"]["result"]["summary"] == "ok"


def test_translate_route_matches_backend_message_and_meta(monkeypatch):
    async def fake_translate(request, principal):
        return {"output": {"translatedText": "hola"}, "reviewStatus": "pending_human_review"}

    monkeypatch.setattr("app.api.ai.translate", fake_translate)
    client = build_client()

    response = client.post(
        "/api/v1/ai/translate",
        json={"text": "hello", "targetLanguage": "Spanish"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Text translated"
    assert payload["meta"] == {"informationOnly": True}
    assert payload["data"]["result"]["output"]["translatedText"] == "hola"


def test_transcribe_route_matches_backend_message_and_meta(monkeypatch):
    async def fake_transcribe(request, principal, file_bytes, file_name, mime_type):
        return {
            "transcript": "hello",
            "language": "en",
            "model": "gpt-4o-transcribe",
            "saved": True,
        }

    monkeypatch.setattr("app.api.ai.transcribe_audio_file", fake_transcribe)
    client = build_client()

    response = client.post(
        "/api/v1/ai/transcribe-audio",
        files={"audio": ("sample.webm", b"abc", "audio/webm")},
        data={"saveTranscript": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Audio transcribed successfully"
    assert payload["meta"] == {}
    assert payload["data"]["saved"] is True


def test_extract_route_rejects_invalid_backend_report_id():
    client = build_client()

    response = client.post(
        "/api/v1/ai/extract-incident-fields",
        json={"reportId": "bad-id", "narrative": "test"},
    )

    assert response.status_code == 400


def test_clarifying_route_rejects_invalid_backend_incident_category():
    client = build_client()

    response = client.post(
        "/api/v1/ai/clarifying-questions",
        json={"narrative": "test", "incidentCategory": "wrong"},
    )

    assert response.status_code == 400
