import base64
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.config.settings import get_settings

from .model import AuthenticatedUserPayload, AuthTokens


def _bcrypt_input(value: str) -> bytes:
    # Node bcrypt effectively truncates at 72 bytes; match that behavior for parity.
    return value.encode("utf-8")[:72]


def _refresh_token_bcrypt_input(refresh_token: str) -> bytes:
    digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    return digest.encode("ascii")


def hash_password(password: str) -> str:
    settings = get_settings()
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_SALT_ROUNDS)
    return bcrypt.hashpw(_bcrypt_input(password), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(_bcrypt_input(password), password_hash.encode("utf-8"))


def hash_refresh_token(refresh_token: str) -> str:
    settings = get_settings()
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_SALT_ROUNDS)
    return bcrypt.hashpw(_refresh_token_bcrypt_input(refresh_token), salt).decode("utf-8")


def verify_refresh_token_hash(refresh_token: str, refresh_token_hash: str) -> bool:
    return bcrypt.checkpw(
        _refresh_token_bcrypt_input(refresh_token), refresh_token_hash.encode("utf-8")
    )


_DURATION_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd])$")


def _parse_duration(duration: str) -> timedelta:
    match = _DURATION_RE.match(duration.strip())
    if not match:
        raise ValueError(f"Unsupported duration format: {duration}")
    value = int(match.group("value"))
    unit = match.group("unit")
    if unit == "s":
        return timedelta(seconds=value)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(days=value)


def _encode_token(payload: dict[str, Any], secret: str, expires_in: str) -> str:
    now = datetime.now(UTC)
    exp = now + _parse_duration(expires_in)
    token_payload = {**payload, "exp": exp, "iat": now, "jti": uuid.uuid4().hex}
    return jwt.encode(token_payload, secret, algorithm="HS256")


def sign_access_token(payload: AuthenticatedUserPayload) -> str:
    settings = get_settings()
    return _encode_token(
        payload.model_dump(by_alias=True),
        settings.JWT_ACCESS_SECRET,
        settings.JWT_ACCESS_EXPIRES_IN,
    )


def sign_refresh_token(payload: AuthenticatedUserPayload) -> str:
    settings = get_settings()
    return _encode_token(
        payload.model_dump(by_alias=True),
        settings.JWT_REFRESH_SECRET,
        settings.JWT_REFRESH_EXPIRES_IN,
    )


def verify_access_token(token: str) -> AuthenticatedUserPayload:
    settings = get_settings()
    decoded = jwt.decode(token, settings.JWT_ACCESS_SECRET, algorithms=["HS256"])
    return AuthenticatedUserPayload.model_validate(decoded)


def verify_refresh_token(token: str) -> AuthenticatedUserPayload:
    settings = get_settings()
    decoded = jwt.decode(token, settings.JWT_REFRESH_SECRET, algorithms=["HS256"])
    return AuthenticatedUserPayload.model_validate(decoded)


def build_auth_tokens(payload: AuthenticatedUserPayload) -> AuthTokens:
    return AuthTokens(
        accessToken=sign_access_token(payload),
        refreshToken=sign_refresh_token(payload),
    )


def derive_full_name_from_email(email: str) -> str:
    local_part = email.split("@")[0].strip() if "@" in email else ""
    if not local_part:
        return "SafeSpeak User"
    return " ".join(
        segment[:1].upper() + segment[1:]
        for segment in re.split(r"[._-]+", local_part)
        if segment
    )


def generate_otp() -> str:
    return f"{int.from_bytes(os.urandom(2), 'big') % 10000:04d}"


def generate_reset_token() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("utf-8")


def generate_nonce() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("utf-8")


def hash_reset_secret(value: str, nonce: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.JWT_REFRESH_SECRET.encode("utf-8"),
        f"{nonce}:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def secrets_match(expected_hash: str, value: str, nonce: str) -> bool:
    actual_hash = hash_reset_secret(value, nonce)
    return hmac.compare_digest(expected_hash, actual_hash)


def fake_reset_request_id() -> str:
    return os.urandom(12).hex()


def encode_auth_data(auth_data: dict[str, Any]) -> str:
    payload = json.dumps(auth_data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode("utf-8")


def invalid_token_to_auth_error(_: InvalidTokenError) -> str:
    return "Invalid authentication token"
