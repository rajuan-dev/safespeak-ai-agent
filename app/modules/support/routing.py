from fastapi import HTTPException, status

from .model import ACTIVE_ADVOCATE_REQUEST_STATUSES, TERMINAL_ADVOCATE_REQUEST_STATUSES


def assert_advocate_request_transition(
    current_status: str, next_status: str, actor_type: str
) -> None:
    if current_status == next_status:
        return
    if current_status in TERMINAL_ADVOCATE_REQUEST_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "This advocate request is already closed")
    admin_transitions = {
        "pending": {"matched", "declined", "cancelled"},
        "matched": {"contact_initiated", "declined", "cancelled"},
        "accepted": {"contact_initiated", "declined", "cancelled"},
        "contact_initiated": {"closed", "declined"},
    }
    user_transitions = {
        "pending": {"cancelled"},
        "matched": {"cancelled"},
        "accepted": {"cancelled"},
    }
    allowed = (
        admin_transitions.get(current_status, set())
        if actor_type == "admin"
        else user_transitions.get(current_status, set())
    )
    if next_status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invalid advocate request status transition")


def active_statuses() -> list[str]:
    return list(ACTIVE_ADVOCATE_REQUEST_STATUSES)
