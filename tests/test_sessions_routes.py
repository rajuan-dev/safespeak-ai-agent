from fastapi.testclient import TestClient

from app.main import app


def test_create_anonymous_session_route_uses_backend_contract():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions/anonymous",
            json={"language": "en", "jurisdiction": "NSW", "safetyGateAccepted": True},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "Anonymous session created"
    assert "sessionToken" in payload["data"]
    assert payload["data"]["session"]["isAnonymous"] is True
