from typing import Any

from app.modules.audit.service import create_audit_log

from .repository import PlatformSettingsRepository, get_platform_settings_repository
from .schema import PlatformSettingsInput


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
    return payload


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


async def get_public_platform_settings(
    *,
    repository: PlatformSettingsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_platform_settings_repository()
    document = await repository.get_or_create()
    return document["published"]


async def get_admin_platform_settings(
    *,
    repository: PlatformSettingsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_platform_settings_repository()
    return _serialize(await repository.get_or_create())


async def update_platform_settings_draft(
    actor_id: str,
    input_data: PlatformSettingsInput,
    *,
    repository: PlatformSettingsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_platform_settings_repository()
    current = await repository.get_or_create()
    draft = _deep_merge(current["draft"], input_data.model_dump(exclude_none=True))
    updated = await repository.update_draft({"draft": draft, "updatedBy": actor_id})
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action="admin.platform_settings.draft.update",
        resource_type="platform_settings",
        metadata={"sections": list(input_data.model_dump(exclude_none=True).keys())},
    )
    return _serialize(updated)


async def publish_platform_settings(
    actor_id: str,
    *,
    repository: PlatformSettingsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_platform_settings_repository()
    current = await repository.get_or_create()
    published = await repository.publish(current["draft"], actor_id)
    await create_audit_log(
        actor_type="user",
        actor_id=actor_id,
        action="admin.platform_settings.publish",
        resource_type="platform_settings",
        metadata={"version": published.get("version")},
    )
    return _serialize(published)
