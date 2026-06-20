from app.core.responses import failure, success


def test_success_envelope_matches_existing_clients():
    result = success("ok", {"value": 1})
    assert result["success"] is True
    assert result["data"] == {"value": 1}
    assert "timestamp" in result


def test_failure_envelope_matches_existing_clients():
    result = failure("bad", error_code="VALIDATION_ERROR", request_id="request-1")
    assert result["success"] is False
    assert result["errorCode"] == "VALIDATION_ERROR"
    assert result["requestId"] == "request-1"

