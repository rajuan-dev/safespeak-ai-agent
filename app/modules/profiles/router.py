from fastapi import APIRouter, Request

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import UpdateProfileInput
from .service import (
    get_community_profile_options,
    get_cultural_profile_options,
    get_faith_profile_options,
    get_language_options,
    get_profile,
    update_profile,
)

router = APIRouter(tags=["profile"])


def _owner(principal: AuthenticatedSessionOrUser) -> dict[str, str | None]:
    return {
        "userId": principal.user_id,
        "sessionId": principal.session_id,
    }


@router.get("/languages")
async def get_languages_route():
    return success("Languages retrieved", {"languages": await get_language_options()})


@router.get("/cultural-profiles")
async def get_cultural_profiles_route():
    return success(
        "Cultural profiles retrieved",
        {"culturalProfiles": await get_cultural_profile_options()},
    )


@router.get("/faith-profiles")
async def get_faith_profiles_route():
    return success("Faith profiles retrieved", {"faithProfiles": await get_faith_profile_options()})


@router.get("/community-profiles")
async def get_community_profiles_route():
    return success(
        "Community profiles retrieved",
        {"communityProfiles": await get_community_profile_options()},
    )


@router.get("/profile")
async def get_profile_route(principal: AuthenticatedSessionOrUser):
    profile = await get_profile(_owner(principal))
    return success("Profile retrieved", {"profile": profile})


@router.patch("/profile")
async def update_profile_route(
    request: Request,
    input_data: UpdateProfileInput,
    principal: AuthenticatedSessionOrUser,
):
    profile = await update_profile(
        _owner(principal),
        input_data,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success("Profile updated", {"profile": profile})
