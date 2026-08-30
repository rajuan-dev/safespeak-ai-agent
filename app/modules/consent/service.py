from fastapi import HTTPException, status

from app.modules.audit.service import create_audit_log
from app.modules.sessions.service import hash_sensitive_value

from .model import DEFAULT_CONSENT_FLAGS
from .repository import ConsentRepository, get_consent_repository
from .schema import UpdateConsentInput, WithdrawConsentInput


def owner_filter(owner: dict[str, str | None]) -> dict[str, str]:
    if owner.get("userId"):
        return {"userId": owner["userId"]}
    if owner.get("sessionId"):
        return {"sessionId": owner["sessionId"]}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")


async def get_current_consent(
    owner: dict[str, str | None],
    *,
    repository: ConsentRepository | None = None,
) -> dict[str, bool]:
    repository = repository or get_consent_repository()
    latest = await repository.find_latest(owner_filter(owner))
    return dict(latest["flags"]) if latest else dict(DEFAULT_CONSENT_FLAGS)


async def get_consent_history(
    owner: dict[str, str | None],
    *,
    repository: ConsentRepository | None = None,
) -> list[dict]:
    repository = repository or get_consent_repository()
    history = await repository.find_history(owner_filter(owner))
    for record in history:
        record["_id"] = str(record["_id"])
        if record.get("userId") is not None:
            record["userId"] = str(record["userId"])
        if record.get("sessionId") is not None:
            record["sessionId"] = str(record["sessionId"])
    return history


async def create_consent_version(
    owner: dict[str, str | None],
    flags: dict[str, bool],
    source: str,
    ip: str | None = None,
    user_agent: str | None = None,
    *,
    repository: ConsentRepository | None = None,
) -> dict[str, bool]:
    repository = repository or get_consent_repository()
    filter_payload = owner_filter(owner)
    latest = await repository.find_latest(filter_payload)
    next_flags = {**(latest["flags"] if latest else DEFAULT_CONSENT_FLAGS), **flags}
    record = await repository.create_record(
        {
            **filter_payload,
            "flags": next_flags,
            "version": (latest["version"] if latest else 0) + 1,
            "source": source,
            "ipHash": hash_sensitive_value(ip) if ip else None,
            "userAgentHash": hash_sensitive_value(user_agent) if user_agent else None,
        }
    )
    await create_audit_log(
        actor_type="user" if owner.get("userId") else "anonymous_session",
        actor_id=owner.get("userId"),
        session_id=owner.get("sessionId"),
        action="consent.update",
        resource_type="consent",
        resource_id=str(record["_id"]),
        ip=ip,
        user_agent=user_agent,
        metadata={"version": record["version"], "changedFlags": list(flags.keys())},
    )
    return record["flags"]


async def update_consent(
    owner: dict[str, str | None],
    input_data: UpdateConsentInput,
    ip: str | None = None,
    user_agent: str | None = None,
    *,
    repository: ConsentRepository | None = None,
) -> dict[str, bool]:
    return await create_consent_version(
        owner,
        input_data.flags,
        input_data.source,
        ip,
        user_agent,
        repository=repository,
    )


async def withdraw_consent(
    owner: dict[str, str | None],
    input_data: WithdrawConsentInput,
    ip: str | None = None,
    user_agent: str | None = None,
    *,
    repository: ConsentRepository | None = None,
) -> dict[str, bool]:
    return await create_consent_version(
        owner,
        {flag: False for flag in input_data.flags},
        input_data.source,
        ip,
        user_agent,
        repository=repository,
    )
