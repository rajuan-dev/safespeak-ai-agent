import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.modules.audit.service import create_audit_log
from app.modules.sessions.repository import SessionsRepository
from app.modules.sessions.schema import (
    AuthenticatedSession,
    CreateAnonymousSessionInput,
)


def generate_secure_token(byte_length: int = 48) -> str:
    return secrets.token_urlsafe(byte_length)


def hash_sensitive_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _to_authenticated_session(document: dict | None) -> AuthenticatedSession:
    if not document:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")

    return AuthenticatedSession(
        id=str(document["_id"]),
        userId=str(document["userId"]) if document.get("userId") else None,
        isAnonymous=bool(document.get("isAnonymous", True)),
        language=document.get("language", "en"),
        jurisdiction=document.get("jurisdiction", "NSW"),
        lga=document.get("lga"),
    )


async def create_anonymous_session(
    input_data: CreateAnonymousSessionInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict:
    session_token = generate_secure_token()
    session_token_hash = hash_sensitive_value(session_token)
    repository = SessionsRepository()
    document = await repository.create_anonymous_session(
        {
            "sessionTokenHash": session_token_hash,
            "isAnonymous": True,
            "safetyGateAcceptedAt": datetime.now(UTC)
            if input_data.safety_gate_accepted
            else None,
            "language": input_data.language or "en",
            "jurisdiction": input_data.jurisdiction or "NSW",
            "lga": input_data.lga,
            "consentSnapshot": {},
        }
    )
    session = _to_authenticated_session(document)
    await create_audit_log(
        actor_type="anonymous_session",
        session_id=session.id,
        action="session.create_anonymous",
        resource_type="session",
        resource_id=session.id,
        ip=ip,
        user_agent=user_agent,
    )
    return {"session": session.model_dump(by_alias=True), "sessionToken": session_token}


async def get_session_by_token(session_token: str) -> AuthenticatedSession:
    repository = SessionsRepository()
    document = await repository.find_by_token_hash(hash_sensitive_value(session_token))
    return _to_authenticated_session(document)


async def convert_session_to_user(
    session_id: str,
    user_id: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuthenticatedSession:
    repository = SessionsRepository()
    document = await repository.convert_to_user(session_id, user_id)
    session = _to_authenticated_session(document)
    await create_audit_log(
        actor_type="anonymous_session",
        actor_id=user_id,
        session_id=session_id,
        action="session.convert_to_user",
        resource_type="session",
        resource_id=session_id,
        ip=ip,
        user_agent=user_agent,
    )
    return session
