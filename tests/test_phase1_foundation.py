from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_http_middleware
from app.main import app


def test_health_route_available_without_api_prefix():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["service"]


def test_not_found_errors_use_safespeak_response_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["errorCode"] == "NOT_FOUND"
    assert response.headers["X-Request-Id"]


def test_validation_errors_use_safespeak_response_envelope():
    validation_app = FastAPI()
    register_http_middleware(validation_app)
    register_exception_handlers(validation_app)

    @validation_app.get("/needs-int")
    async def needs_int(value: int):
        return {"value": value}

    with TestClient(validation_app) as client:
        response = client.get("/needs-int", params={"value": "abc"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["message"] == "Validation failed"
    assert payload["errorCode"] == "VALIDATION_ERROR"
    assert isinstance(payload["errors"], list)
