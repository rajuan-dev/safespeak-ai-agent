from app.core.response import error_response, success_response


def success(message: str, data=None, meta=None):
    return success_response(message, data=data, meta=meta)


def failure(message: str, *, error_code: str, request_id: str | None = None, errors=None):
    return error_response(
        message,
        error_code=error_code,
        request_id=request_id,
        errors=errors,
    )
