from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException, status

from app.config.settings import get_settings
from app.core.permissions import is_admin_role, is_public_role
from app.modules.audit.service import create_audit_log

from .model import AuthData, AuthenticatedUserPayload, SafeUser
from .repository import AuthRepository, get_auth_repository
from .schema import (
    ChangePasswordInput,
    ForgotPasswordInput,
    LoginInput,
    RegisterInput,
    ResetPasswordInput,
    UpdateCurrentUserProfileInput,
    VerifyPasswordResetOtpInput,
)
from .security import (
    build_auth_tokens,
    derive_full_name_from_email,
    encode_auth_data,
    fake_reset_request_id,
    generate_nonce,
    generate_otp,
    generate_reset_token,
    hash_password,
    hash_refresh_token,
    hash_reset_secret,
    secrets_match,
    verify_password,
    verify_refresh_token,
    verify_refresh_token_hash,
)

PASSWORD_RESET_EXPIRY_MINUTES = 15
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES = 10
PASSWORD_RESET_MAX_ATTEMPTS = 5


def minutes_from_now(minutes: int) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def reset_request_expired(expires_at: datetime | None) -> bool:
    return not expires_at or expires_at <= datetime.now(UTC)


def to_safe_user(user: dict[str, Any] | None) -> SafeUser:
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return SafeUser(
        id=str(user["_id"]),
        email=user["email"],
        fullName=user["fullName"],
        contactNo=user.get("contactNo"),
        avatarUrl=user.get("avatarUrl"),
        role=user["role"],
        status=user["status"],
        isEmailVerified=user.get("isEmailVerified", False),
        lastLoginAt=user.get("lastLoginAt"),
        createdAt=user["createdAt"],
        updatedAt=user["updatedAt"],
    )


async def issue_tokens(
    repository: AuthRepository,
    user_id: str,
    role: str,
) -> dict[str, Any]:
    tokens = build_auth_tokens(AuthenticatedUserPayload(userId=user_id, role=role))
    refresh_token_hash = hash_refresh_token(tokens.refresh_token)
    await repository.update_refresh_token_hash(user_id, refresh_token_hash)
    return tokens.model_dump(by_alias=True)


async def audit_password_reset(
    action: str,
    audience: str,
    *,
    user: dict[str, Any] | None = None,
    resource_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    actor_type = "system"
    if user:
        actor_type = "admin" if is_admin_role(user["role"]) else "user"
    await create_audit_log(
        actor_type=actor_type,
        actor_id=str(user["_id"]) if user else None,
        action=action,
        resource_type="auth",
        resource_id=resource_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"audience": audience, **(metadata or {})},
    )


async def register_user(
    input_data: RegisterInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    email = input_data.email.lower()
    existing_user = await repository.find_user_by_email(email)
    if existing_user:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")

    user = await repository.create_user(
        {
            "email": email,
            "fullName": input_data.full_name or derive_full_name_from_email(email),
            "passwordHash": hash_password(input_data.password),
            "role": "public_user",
            "status": "active",
            "authProvider": "local",
            "isEmailVerified": False,
        }
    )
    safe_user = to_safe_user(user)
    tokens = await issue_tokens(repository, safe_user.id, safe_user.role)
    await create_audit_log(
        actor_type="user",
        actor_id=safe_user.id,
        action="auth.register",
        resource_type="auth",
        resource_id=safe_user.id,
        ip=ip,
        user_agent=user_agent,
    )
    return AuthData(user=safe_user, tokens=tokens).model_dump(by_alias=True)


async def login_user(
    input_data: LoginInput,
    admin_only: bool,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    user = await repository.find_user_by_email(input_data.email.lower())
    if not user or not verify_password(input_data.password, user["passwordHash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user["status"] != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User account is not active")
    if admin_only and not is_admin_role(user["role"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access is required")
    if not admin_only and not is_public_role(user["role"]):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Use the admin login endpoint for this account"
        )

    safe_user = to_safe_user(user)
    tokens = await issue_tokens(repository, safe_user.id, safe_user.role)
    await create_audit_log(
        actor_type="admin" if admin_only else "user",
        actor_id=safe_user.id,
        action="auth.admin_login" if admin_only else "auth.login",
        resource_type="auth",
        resource_id=safe_user.id,
        ip=ip,
        user_agent=user_agent,
    )
    return AuthData(user=safe_user, tokens=tokens).model_dump(by_alias=True)


async def login_with_google_profile(
    *,
    google_id: str,
    email: str,
    full_name: str,
    avatar_url: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    user = await repository.find_user_by_google_or_email(google_id, email.lower())
    action = "auth.google_login"

    if user:
        if user["status"] != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "User account is not active")
        if not is_public_role(user["role"]):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Use the admin login endpoint for this account"
            )
        user = await repository.update_user(
            str(user["_id"]),
            {
                "googleId": user.get("googleId") or google_id,
                "authProvider": "local" if user.get("authProvider") == "local" else "google",
                "isEmailVerified": True,
                "fullName": user.get("fullName") or full_name,
                "avatarUrl": avatar_url or user.get("avatarUrl"),
            },
        )
    else:
        action = "auth.google_register"
        user = await repository.create_user(
            {
                "email": email.lower(),
                "fullName": full_name,
                "googleId": google_id,
                "authProvider": "google",
                "avatarUrl": avatar_url,
                "passwordHash": hash_password(generate_reset_token()),
                "role": "public_user",
                "status": "active",
                "isEmailVerified": True,
            }
        )

    safe_user = to_safe_user(user)
    tokens = await issue_tokens(repository, safe_user.id, safe_user.role)
    await create_audit_log(
        actor_type="user",
        actor_id=safe_user.id,
        action=action,
        resource_type="auth",
        resource_id=safe_user.id,
        ip=ip,
        user_agent=user_agent,
    )
    return AuthData(user=safe_user, tokens=tokens).model_dump(by_alias=True)


async def refresh_user_token(
    refresh_token: str,
    *,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    try:
        payload = verify_refresh_token(refresh_token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc

    user = await repository.find_user_by_id(payload.user_id)
    if not user or not user.get("refreshTokenHash"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if (
        not verify_refresh_token_hash(refresh_token, user["refreshTokenHash"])
        or user["status"] != "active"
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    safe_user = to_safe_user(user)
    tokens = await issue_tokens(repository, safe_user.id, safe_user.role)
    return AuthData(user=safe_user, tokens=tokens).model_dump(by_alias=True)


async def logout_user(user_id: str | None, repository: AuthRepository | None = None) -> None:
    if not user_id:
        return
    repository = repository or get_auth_repository()
    await repository.unset_refresh_token_hash(user_id)


async def change_user_password(
    user_id: str,
    input_data: ChangePasswordInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    user = await repository.find_user_by_id(user_id)
    if not user or user["status"] != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token")
    if not verify_password(input_data.current_password, user["passwordHash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")

    user = await repository.update_user(
        user_id,
        {"passwordHash": hash_password(input_data.new_password)},
    )
    safe_user = to_safe_user(user)
    await create_audit_log(
        actor_type="admin" if is_admin_role(safe_user.role) else "user",
        actor_id=safe_user.id,
        action="auth.change_password",
        resource_type="auth",
        resource_id=safe_user.id,
        ip=ip,
        user_agent=user_agent,
    )
    return safe_user.model_dump(by_alias=True)


async def update_current_user_profile(
    user_id: str,
    input_data: UpdateCurrentUserProfileInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    user = await repository.find_user_by_id(user_id)
    if not user or user["status"] != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token")

    changed_fields: list[str] = []
    updates: dict[str, Any] = {}
    if input_data.full_name is not None and input_data.full_name != user["fullName"]:
        updates["fullName"] = input_data.full_name
        changed_fields.append("fullName")
    if input_data.email is not None:
        next_email = input_data.email.lower()
        if next_email != user["email"]:
            existing = await repository.find_user_by_email(next_email)
            if existing and str(existing["_id"]) != str(user["_id"]):
                raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
            updates["email"] = next_email
            changed_fields.append("email")
    if (
        input_data.contact_no is not None
        and input_data.contact_no != (user.get("contactNo") or "")
    ):
        updates["contactNo"] = input_data.contact_no
        changed_fields.append("contactNo")

    if updates:
        user = await repository.update_user(user_id, updates)
    safe_user = to_safe_user(user)
    await create_audit_log(
        actor_type="admin" if is_admin_role(safe_user.role) else "user",
        actor_id=safe_user.id,
        action="auth.profile.update",
        resource_type="auth",
        resource_id=safe_user.id,
        ip=ip,
        user_agent=user_agent,
        metadata={"changedFields": changed_fields},
    )
    return safe_user.model_dump(by_alias=True)


def is_eligible_for_password_reset(user: dict[str, Any], audience: str) -> bool:
    if user["status"] != "active":
        return False
    return is_admin_role(user["role"]) if audience == "admin" else is_public_role(user["role"])


async def write_password_reset_outbox(
    *,
    request_id: str,
    email: str,
    full_name: str,
    otp: str,
    expires_at: datetime,
) -> str:
    settings = get_settings()
    Path(settings.AUTH_RESET_OUTBOX_PATH).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat().replace(":", "-").replace(".", "-")
    file_name = f"{timestamp}-{request_id}.json"
    outbox_path = Path(settings.AUTH_RESET_OUTBOX_PATH) / file_name
    email_text = (
        f"Hello {full_name}, your SafeSpeak password reset code is {otp}. "
        f"It expires at {expires_at.isoformat()}."
    )
    outbox_path.write_text(
        (
            "{\n"
            f'  "type": "password_reset_otp",\n'
            f'  "to": "{email}",\n'
            '  "subject": "SafeSpeak password reset code",\n'
            f'  "text": "{email_text}",\n'
            f'  "otp": "{otp}",\n'
            f'  "expiresAt": "{expires_at.isoformat()}",\n'
            f'  "requestId": "{request_id}",\n'
            f'  "createdAt": "{datetime.now(UTC).isoformat()}"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    return str(outbox_path)


async def deliver_password_reset_otp(
    *,
    request_id: str,
    email: str,
    full_name: str,
    otp: str,
    expires_at: datetime,
) -> dict[str, str | None]:
    settings = get_settings()
    payload = {
        "type": "password_reset_otp",
        "to": email,
        "subject": "SafeSpeak password reset code",
        "text": (
            f"Hello {full_name}, your SafeSpeak password reset code is {otp}. "
            f"It expires at {expires_at.isoformat()}."
        ),
        "otp": otp,
        "expiresAt": expires_at.isoformat(),
        "requestId": request_id,
    }
    if settings.AUTH_RESET_EMAIL_WEBHOOK_URL:
        headers = {"content-type": "application/json"}
        if settings.AUTH_RESET_EMAIL_WEBHOOK_TOKEN:
            headers["authorization"] = f"Bearer {settings.AUTH_RESET_EMAIL_WEBHOOK_TOKEN}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                settings.AUTH_RESET_EMAIL_WEBHOOK_URL,
                json=payload,
                headers=headers,
            )
        if response.status_code >= 400:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Password reset email could not be queued",
            )
        return {"mode": "webhook", "reference": None}

    if get_settings().ENVIRONMENT == "production":
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Password reset delivery is not configured",
        )

    return {
        "mode": "development_outbox",
        "reference": await write_password_reset_outbox(
            request_id=request_id,
            email=email,
            full_name=full_name,
            otp=otp,
            expires_at=expires_at,
        ),
    }


async def request_password_reset(
    input_data: ForgotPasswordInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    email = input_data.email.lower()
    audience = input_data.audience
    expires_at = minutes_from_now(PASSWORD_RESET_EXPIRY_MINUTES)

    settings = get_settings()
    if settings.ENVIRONMENT == "production" and not settings.AUTH_RESET_EMAIL_WEBHOOK_URL:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Password reset delivery is not configured",
        )

    user = await repository.find_user_by_email(email)
    if not user or not is_eligible_for_password_reset(user, audience):
        await audit_password_reset(
            "auth.password_reset.request_ignored",
            audience,
            ip=ip,
            user_agent=user_agent,
            metadata={"reason": "ineligible_or_missing_account"},
        )
        return {
            "resetRequestId": fake_reset_request_id(),
            "expiresAt": expires_at.isoformat(),
        }

    await repository.expire_active_reset_requests(str(user["_id"]), audience)
    otp = generate_otp()
    otp_nonce = generate_nonce()
    request = await repository.create_password_reset_request(
        {
            "userId": user["_id"],
            "email": email,
            "audience": audience,
            "otpHash": hash_reset_secret(otp, otp_nonce),
            "otpNonce": otp_nonce,
            "otpAttempts": 0,
            "maxOtpAttempts": PASSWORD_RESET_MAX_ATTEMPTS,
            "expiresAt": expires_at,
        }
    )
    delivery = await deliver_password_reset_otp(
        request_id=str(request["_id"]),
        email=email,
        full_name=user["fullName"],
        otp=otp,
        expires_at=expires_at,
    )
    await repository.update_password_reset_request(
        str(request["_id"]),
        {
            "deliveredAt": datetime.now(UTC),
            "deliveryMode": delivery["mode"],
            "deliveryReference": delivery["reference"],
        },
    )
    await audit_password_reset(
        "auth.password_reset.request",
        audience,
        user=user,
        resource_id=str(request["_id"]),
        ip=ip,
        user_agent=user_agent,
        metadata={"deliveryMode": delivery["mode"]},
    )
    result = {"resetRequestId": str(request["_id"]), "expiresAt": expires_at.isoformat()}
    if get_settings().ENVIRONMENT != "production":
        result["debugOtp"] = otp
    return result


async def verify_password_reset_otp(
    input_data: VerifyPasswordResetOtpInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    request = await repository.find_password_reset_request(
        input_data.reset_request_id,
        input_data.email.lower(),
        input_data.audience,
    )
    if (
        not request
        or request.get("usedAt")
        or reset_request_expired(request.get("expiresAt"))
        or request.get("otpAttempts", 0)
        >= request.get("maxOtpAttempts", PASSWORD_RESET_MAX_ATTEMPTS)
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired verification code"
        )

    request["otpAttempts"] = request.get("otpAttempts", 0) + 1
    if not secrets_match(request["otpHash"], input_data.otp, request["otpNonce"]):
        updates = {"otpAttempts": request["otpAttempts"]}
        if request["otpAttempts"] >= request.get("maxOtpAttempts", PASSWORD_RESET_MAX_ATTEMPTS):
            updates["expiresAt"] = datetime.now(UTC)
        await repository.update_password_reset_request(input_data.reset_request_id, updates)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired verification code"
        )

    reset_token = generate_reset_token()
    reset_token_nonce = generate_nonce()
    reset_token_expires_at = minutes_from_now(PASSWORD_RESET_TOKEN_EXPIRY_MINUTES)
    user = await repository.find_user_by_id(str(request["userId"]))
    await repository.update_password_reset_request(
        input_data.reset_request_id,
        {
            "otpAttempts": request["otpAttempts"],
            "verifiedAt": datetime.now(UTC),
            "resetTokenHash": hash_reset_secret(reset_token, reset_token_nonce),
            "resetTokenNonce": reset_token_nonce,
            "resetTokenExpiresAt": reset_token_expires_at,
        },
    )
    await audit_password_reset(
        "auth.password_reset.verify_otp",
        input_data.audience,
        user=user,
        resource_id=input_data.reset_request_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"attempts": request["otpAttempts"]},
    )
    return {
        "resetToken": reset_token,
        "resetTokenExpiresAt": reset_token_expires_at.isoformat(),
    }


async def reset_user_password_with_token(
    input_data: ResetPasswordInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> None:
    repository = repository or get_auth_repository()
    request = await repository.find_password_reset_request(
        input_data.reset_request_id,
        input_data.email.lower(),
        input_data.audience,
    )
    if (
        not request
        or request.get("usedAt")
        or reset_request_expired(request.get("expiresAt"))
        or not request.get("verifiedAt")
        or not request.get("resetTokenHash")
        or not request.get("resetTokenNonce")
        or reset_request_expired(request.get("resetTokenExpiresAt"))
        or not secrets_match(
            request["resetTokenHash"], input_data.reset_token, request["resetTokenNonce"]
        )
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired password reset session"
        )

    user = await repository.find_user_by_id(str(request["userId"]))
    if not user or not is_eligible_for_password_reset(user, input_data.audience):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired password reset session"
        )

    await repository.update_user(
        str(user["_id"]),
        {
            "passwordHash": hash_password(input_data.new_password),
            "refreshTokenHash": None,
        },
    )
    await repository.update_password_reset_request(
        input_data.reset_request_id, {"usedAt": datetime.now(UTC)}
    )
    await repository.expire_other_password_reset_requests(
        str(user["_id"]), input_data.audience, input_data.reset_request_id
    )
    await audit_password_reset(
        "auth.password_reset.complete",
        input_data.audience,
        user=user,
        resource_id=input_data.reset_request_id,
        ip=ip,
        user_agent=user_agent,
    )


async def deactivate_user_account(
    user_id: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    user = await repository.update_user(user_id, {"status": "inactive", "refreshTokenHash": None})
    safe_user = to_safe_user(user)
    await create_audit_log(
        actor_type="user",
        actor_id=safe_user.id,
        action="auth.deactivate",
        resource_type="auth",
        resource_id=safe_user.id,
        ip=ip,
        user_agent=user_agent,
    )
    return safe_user.model_dump(by_alias=True)


async def get_safe_user_by_id(
    user_id: str,
    *,
    repository: AuthRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_auth_repository()
    return to_safe_user(await repository.find_user_by_id(user_id)).model_dump(by_alias=True)


def get_google_oauth_missing_config() -> list[str]:
    settings = get_settings()
    missing = []
    if not settings.GOOGLE_CLIENT_ID:
        missing.append("GOOGLE_CLIENT_ID")
    if not settings.GOOGLE_CLIENT_SECRET:
        missing.append("GOOGLE_CLIENT_SECRET")
    return missing


def is_google_oauth_configured() -> bool:
    return len(get_google_oauth_missing_config()) == 0


def get_google_callback_url() -> str:
    return get_settings().GOOGLE_CALLBACK_URL or "/api/auth/google/callback"


def build_google_login_redirect_url() -> str:
    settings = get_settings()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID or "",
        "redirect_uri": get_google_callback_url(),
        "response_type": "code",
        "scope": "profile email",
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


async def exchange_google_code_for_profile(code: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID or "",
                "client_secret": settings.GOOGLE_CLIENT_SECRET or "",
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": get_google_callback_url(),
            },
        )
        token_response.raise_for_status()
        token_payload = token_response.json()
        access_token = token_payload.get("access_token")
        if not access_token:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Google sign-in was cancelled or could not be completed.",
            )
        profile_response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    email = profile.get("email")
    if not email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Google account did not provide an email address",
        )
    return {
        "googleId": profile.get("sub", ""),
        "email": email,
        "fullName": profile.get("name") or email.split("@")[0] or "SafeSpeak User",
        "avatarUrl": profile.get("picture"),
    }


def build_client_auth_callback_redirect(auth_data: dict[str, Any]) -> str:
    base_url = get_settings().CLIENT_URL.rstrip("/")
    encoded_auth = encode_auth_data(auth_data)
    return f"{base_url}/auth/callback#auth={encoded_auth}"


def build_client_auth_error_redirect(message: str) -> str:
    encoded_message = quote(message, safe="")
    base_url = get_settings().CLIENT_URL.rstrip("/")
    return f"{base_url}/login?authError={encoded_message}"
