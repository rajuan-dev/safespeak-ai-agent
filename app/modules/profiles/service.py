from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException, status

from app.modules.audit.service import create_audit_log

from .model import DEFAULT_PROFILE_JURISDICTION, DEFAULT_PROFILE_LANGUAGE
from .repository import ProfilesRepository, get_profiles_repository
from .schema import UpdateProfileInput


def owner_filter(owner: dict[str, str | None]) -> dict[str, str]:
    if owner.get("userId"):
        return {"userId": owner["userId"]}
    if owner.get("sessionId"):
        return {"sessionId": owner["sessionId"]}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")


def _unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        trimmed = value.strip()
        key = trimmed.lower()
        if not trimmed or key in seen:
            continue
        seen.add(key)
        result.append(trimmed)
    return result


async def get_profile(
    owner: dict[str, str | None],
    *,
    repository: ProfilesRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_profiles_repository()
    profile = await repository.find_one(owner_filter(owner))
    if profile:
        profile["_id"] = str(profile["_id"])
        if profile.get("userId") is not None:
            profile["userId"] = str(profile["userId"])
        if profile.get("sessionId") is not None:
            profile["sessionId"] = str(profile["sessionId"])
        return profile
    filter_payload = owner_filter(owner)
    return {
        **filter_payload,
        "preferredLanguage": DEFAULT_PROFILE_LANGUAGE,
        "jurisdiction": DEFAULT_PROFILE_JURISDICTION,
        "referralSharingPreference": False,
        "accessibilityPreferences": {},
    }


async def update_profile(
    owner: dict[str, str | None],
    input_data: UpdateProfileInput,
    ip: str | None = None,
    user_agent: str | None = None,
    *,
    repository: ProfilesRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_profiles_repository()
    filter_payload = owner_filter(owner)
    payload = input_data.model_dump(by_alias=True, exclude_none=True)
    profile = await repository.upsert_one(filter_payload, payload)
    await create_audit_log(
        actor_type="user" if owner.get("userId") else "anonymous_session",
        actor_id=owner.get("userId"),
        session_id=owner.get("sessionId"),
        action="profile.update",
        resource_type="profile",
        resource_id=str(profile["_id"]),
        ip=ip,
        user_agent=user_agent,
        metadata={"changedFields": list(payload.keys())},
    )
    profile["_id"] = str(profile["_id"])
    if profile.get("userId") is not None:
        profile["userId"] = str(profile["userId"])
    if profile.get("sessionId") is not None:
        profile["sessionId"] = str(profile["sessionId"])
    return profile


async def get_language_options(
    *,
    repository: ProfilesRepository | None = None,
) -> list[dict[str, str]]:
    repository = repository or get_profiles_repository()
    records = await repository.list_active_language_taxonomies()
    return [
        {
            "code": record.get("key") or "",
            "label": record.get("label") or record.get("key") or "",
        }
        for record in records
    ]


async def _get_profile_options(
    profile_group: str,
    *,
    repository: ProfilesRepository | None = None,
) -> list[str]:
    repository = repository or get_profiles_repository()
    taxonomy_records = await repository.list_active_culture_taxonomies()
    taxonomy_values = [
        record["label"]
        for record in taxonomy_records
        if (record.get("metadata") or {}).get("profileGroup") == profile_group
    ]
    managed_records = await repository.list_managed_profiles(profile_group)
    managed_values = [record["name"] for record in managed_records]
    return _unique_strings([*taxonomy_values, *managed_values])


async def get_cultural_profile_options(
    *,
    repository: ProfilesRepository | None = None,
) -> list[str]:
    return await _get_profile_options("cultural", repository=repository)


async def get_faith_profile_options(
    *,
    repository: ProfilesRepository | None = None,
) -> list[str]:
    return await _get_profile_options("faith", repository=repository)


async def get_community_profile_options(
    *,
    repository: ProfilesRepository | None = None,
) -> list[str]:
    return await _get_profile_options("community", repository=repository)
