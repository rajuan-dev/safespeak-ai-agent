from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core.responses import success

from .dependencies import AuthenticatedUser
from .schema import (
    ChangePasswordInput,
    DeactivateAccountInput,
    ForgotPasswordInput,
    LoginInput,
    RefreshTokenInput,
    RegisterInput,
    ResetPasswordInput,
    UpdateCurrentUserProfileInput,
    VerifyPasswordResetOtpInput,
)
from .service import (
    build_client_auth_callback_redirect,
    build_client_auth_error_redirect,
    build_google_login_redirect_url,
    change_user_password,
    deactivate_user_account,
    exchange_google_code_for_profile,
    get_google_oauth_missing_config,
    get_safe_user_by_id,
    is_google_oauth_configured,
    login_user,
    login_with_google_profile,
    logout_user,
    refresh_user_token,
    register_user,
    request_password_reset,
    reset_user_password_with_token,
    update_current_user_profile,
    verify_password_reset_otp,
)

router = APIRouter(prefix="/auth", tags=["auth"])
google_router = APIRouter(prefix="/auth", tags=["auth"])


def create_google_oauth_config_error() -> HTTPException:
    missing = get_google_oauth_missing_config()
    message = (
        f"Google OAuth is not configured. Missing: {', '.join(missing)}"
        if missing
        else "Google OAuth is not configured"
    )
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, message)


@router.post("/register", status_code=201)
async def register_route(request: Request, input_data: RegisterInput):
    result = await register_user(
        input_data,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("User registered successfully", result)


@router.post("/login")
async def login_route(request: Request, input_data: LoginInput):
    result = await login_user(
        input_data,
        False,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Login successful", result)


@router.post("/admin/login")
async def admin_login_route(request: Request, input_data: LoginInput):
    result = await login_user(
        input_data,
        True,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Admin login successful", result)


@router.post("/refresh")
async def refresh_route(input_data: RefreshTokenInput):
    result = await refresh_user_token(input_data.refresh_token)
    return success("Token refreshed successfully", result)


@router.post("/forgot-password")
async def forgot_password_route(request: Request, input_data: ForgotPasswordInput):
    result = await request_password_reset(
        input_data,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("If an eligible account exists, a verification code has been sent", result)


@router.post("/verify-reset-otp")
async def verify_reset_otp_route(
    request: Request, input_data: VerifyPasswordResetOtpInput
):
    result = await verify_password_reset_otp(
        input_data,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Verification code accepted", result)


@router.post("/reset-password")
async def reset_password_route(request: Request, input_data: ResetPasswordInput):
    await reset_user_password_with_token(
        input_data,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Password reset successfully", None)


@router.post("/logout")
async def logout_route(principal: AuthenticatedUser):
    await logout_user(principal.user_id)
    return success("Logout successful", None)


@router.post("/change-password")
async def change_password_route(
    request: Request,
    input_data: ChangePasswordInput,
    principal: AuthenticatedUser,
):
    user = await change_user_password(
        principal.user_id,
        input_data,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Password updated successfully", {"user": user})


@router.get("/me")
async def me_route(principal: AuthenticatedUser):
    user = await get_safe_user_by_id(principal.user_id)
    return success("Current user retrieved successfully", {"user": user})


@router.patch("/me")
async def update_me_route(
    request: Request,
    input_data: UpdateCurrentUserProfileInput,
    principal: AuthenticatedUser,
):
    user = await update_current_user_profile(
        principal.user_id,
        input_data,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Current user updated successfully", {"user": user})


@router.post("/deactivate")
async def deactivate_route(
    request: Request,
    _: DeactivateAccountInput,
    principal: AuthenticatedUser,
):
    user = await deactivate_user_account(
        principal.user_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success("Account deactivated", {"user": user})


@router.get("/google")
@google_router.get("/google")
async def google_login_route():
    if not is_google_oauth_configured():
        raise create_google_oauth_config_error()
    return RedirectResponse(build_google_login_redirect_url(), status_code=302)


@router.get("/google/callback")
@google_router.get("/google/callback")
async def google_callback_route(
    request: Request,
    code: str | None = None,
    error: str | None = None,
):
    if not is_google_oauth_configured():
        raise create_google_oauth_config_error()
    if error:
        return RedirectResponse(
            build_client_auth_error_redirect("Google sign-in failed. Please try again."),
            status_code=302,
        )
    if not code:
        return RedirectResponse(
            build_client_auth_error_redirect(
                "Google sign-in was cancelled or could not be completed."
            ),
            status_code=302,
        )

    try:
        profile = await exchange_google_code_for_profile(code)
        auth_data = await login_with_google_profile(
            google_id=profile["googleId"],
            email=profile["email"],
            full_name=profile["fullName"],
            avatar_url=profile.get("avatarUrl"),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except HTTPException as exc:
        return RedirectResponse(
            build_client_auth_error_redirect(str(exc.detail)),
            status_code=302,
        )
    except Exception:
        return RedirectResponse(
            build_client_auth_error_redirect("Google sign-in failed. Please try again."),
            status_code=302,
        )

    return RedirectResponse(build_client_auth_callback_redirect(auth_data), status_code=302)
