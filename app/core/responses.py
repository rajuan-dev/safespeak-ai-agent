from datetime import UTC, datetime
from typing import Any


def success(message: str, data: Any = None, meta: Any = None) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
        "meta": meta,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def failure(
    message: str,
    *,
    error_code: str,
    request_id: str | None = None,
    errors: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "data": None,
        "meta": None,
        "errors": errors or [],
        "errorCode": error_code,
        "requestId": request_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }

