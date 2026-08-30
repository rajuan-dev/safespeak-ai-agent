from fastapi import APIRouter

from app.core.responses import success

from .dependencies import PlatformSettingsAdmin
from .schema import PlatformSettingsInput
from .service import (
    get_admin_platform_settings,
    get_public_platform_settings,
    publish_platform_settings,
    update_platform_settings_draft,
)

router = APIRouter(prefix="/platform-settings", tags=["platform-settings"])
admin_router = APIRouter(prefix="/admin/platform-settings", tags=["admin-platform-settings"])


@router.get("")
async def get_public_platform_settings_route():
    platform_settings = await get_public_platform_settings()
    return success("Platform settings retrieved", {"platformSettings": platform_settings})


@admin_router.get("")
async def get_admin_platform_settings_route(principal: PlatformSettingsAdmin):
    platform_settings = await get_admin_platform_settings()
    return success("Admin platform settings retrieved", {"platformSettings": platform_settings})


@admin_router.patch("/draft")
async def update_platform_settings_draft_route(
    input_data: PlatformSettingsInput,
    principal: PlatformSettingsAdmin,
):
    platform_settings = await update_platform_settings_draft(principal.user_id or "", input_data)
    return success("Platform settings draft updated", {"platformSettings": platform_settings})


@admin_router.post("/publish")
async def publish_platform_settings_route(principal: PlatformSettingsAdmin):
    platform_settings = await publish_platform_settings(principal.user_id or "")
    return success("Platform settings published", {"platformSettings": platform_settings})
