from typing import Any

from fastapi import HTTPException, status

from .repository import UsersRepository, get_users_repository
from .schema import UpdateUserInput


def to_safe_user(user: dict[str, Any] | None) -> dict[str, Any]:
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "fullName": user["fullName"],
        "contactNo": user.get("contactNo"),
        "avatarUrl": user.get("avatarUrl"),
        "role": user["role"],
        "status": user["status"],
        "isEmailVerified": user.get("isEmailVerified", False),
        "lastLoginAt": user.get("lastLoginAt"),
        "createdAt": user["createdAt"],
        "updatedAt": user["updatedAt"],
    }


async def get_current_user(
    user_id: str,
    *,
    repository: UsersRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_users_repository()
    return to_safe_user(await repository.find_by_id(user_id))


async def update_current_user(
    user_id: str,
    input_data: UpdateUserInput,
    *,
    repository: UsersRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_users_repository()
    user = await repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    updates: dict[str, Any] = {}
    if input_data.full_name is not None:
        updates["fullName"] = input_data.full_name
    if input_data.contact_no is not None:
        updates["contactNo"] = input_data.contact_no
    if input_data.email is not None and input_data.email != user["email"]:
        existing = await repository.find_by_email(input_data.email)
        if existing and str(existing["_id"]) != str(user["_id"]):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
        updates["email"] = input_data.email

    if updates:
        user = await repository.update_by_id(user_id, updates)

    return to_safe_user(user)
