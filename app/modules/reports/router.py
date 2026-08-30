from fastapi import APIRouter, Request, status

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import (
    AcknowledgeSubmissionInput,
    CreateReportInput,
    CreateSubmissionInput,
    MarkInfoOnlyInput,
    RequestDeleteInput,
    SubmissionPreviewInput,
    UpdateReportInput,
    WithdrawReportInput,
)
from .service import (
    acknowledge_submission,
    create_or_update_report_from_conversation,
    create_report,
    create_submission,
    create_submission_previews,
    delete_report,
    get_report,
    get_report_destinations,
    get_report_status,
    get_report_timeline,
    list_report_submissions,
    list_reports,
    mark_report_info_only,
    request_report_delete,
    update_report,
    withdraw_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _owner(principal: AuthenticatedSessionOrUser) -> dict[str, str | None]:
    return {"userId": principal.user_id, "sessionId": principal.session_id}


def _request_context(request: Request) -> tuple[str | None, str | None]:
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/from-conversation/{conversationSessionId}", status_code=status.HTTP_201_CREATED)
async def create_report_from_conversation_route(
    request: Request,
    conversationSessionId: str,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    report = await create_or_update_report_from_conversation(
        conversationSessionId,
        _owner(principal),
        ip=ip,
        user_agent=user_agent,
    )
    return success("Report created from conversation", {"report": report})


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_report_route(
    request: Request,
    input_data: CreateReportInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    report = await create_report(_owner(principal), input_data, ip=ip, user_agent=user_agent)
    return success("Report created", {"report": report})


@router.get("/")
async def list_reports_route(principal: AuthenticatedSessionOrUser):
    reports = await list_reports(_owner(principal))
    return success("Reports retrieved", {"reports": reports})


@router.get("/{id}")
async def get_report_route(id: str, principal: AuthenticatedSessionOrUser):
    report = await get_report(id, _owner(principal))
    return success("Report retrieved", {"report": report})


@router.patch("/{id}")
async def update_report_route(
    request: Request,
    id: str,
    input_data: UpdateReportInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    report = await update_report(id, _owner(principal), input_data, ip=ip, user_agent=user_agent)
    return success("Report updated", {"report": report})


@router.delete("/{id}")
async def delete_report_route(request: Request, id: str, principal: AuthenticatedSessionOrUser):
    ip, user_agent = _request_context(request)
    report = await delete_report(id, _owner(principal), ip=ip, user_agent=user_agent)
    return success("Report deleted", {"report": report})


@router.post("/{id}/mark-info-only")
async def mark_info_only_route(
    request: Request,
    id: str,
    input_data: MarkInfoOnlyInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    report = await mark_report_info_only(
        id, _owner(principal), input_data, ip=ip, user_agent=user_agent
    )
    return success("Report marked as info only", {"report": report})


@router.post("/{id}/withdraw")
async def withdraw_report_route(
    request: Request,
    id: str,
    input_data: WithdrawReportInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    report = await withdraw_report(id, _owner(principal), input_data, ip=ip, user_agent=user_agent)
    return success("Report withdrawn", {"report": report})


@router.post("/{id}/request-delete")
async def request_delete_route(
    request: Request,
    id: str,
    input_data: RequestDeleteInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    report = await request_report_delete(
        id, _owner(principal), input_data, ip=ip, user_agent=user_agent
    )
    return success("Report deletion requested", {"report": report})


@router.get("/{id}/status")
async def report_status_route(id: str, principal: AuthenticatedSessionOrUser):
    report_status = await get_report_status(id, _owner(principal))
    return success("Report status retrieved", {"status": report_status})


@router.get("/{id}/timeline")
async def report_timeline_route(id: str, principal: AuthenticatedSessionOrUser):
    timeline = await get_report_timeline(id, _owner(principal))
    return success("Report timeline retrieved", {"timeline": timeline})


@router.get("/{id}/destinations")
async def report_destinations_route(id: str, principal: AuthenticatedSessionOrUser):
    destinations = await get_report_destinations(id, _owner(principal))
    return success("Report destinations retrieved", {"destinations": destinations})


@router.get("/{id}/submissions")
async def report_submissions_route(id: str, principal: AuthenticatedSessionOrUser):
    submissions = await list_report_submissions(id, _owner(principal))
    return success("Report submissions retrieved", {"submissions": submissions})


@router.post("/{id}/submission-previews")
async def report_submission_previews_route(
    id: str,
    input_data: SubmissionPreviewInput,
    principal: AuthenticatedSessionOrUser,
):
    previews = await create_submission_previews(id, _owner(principal), input_data)
    return success("Report submission previews generated", {"previews": previews})


@router.post("/{id}/submissions", status_code=status.HTTP_201_CREATED)
async def create_submission_route(
    request: Request,
    id: str,
    input_data: CreateSubmissionInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    submission = await create_submission(
        id, _owner(principal), input_data, ip=ip, user_agent=user_agent
    )
    return success("Report submission created", {"submission": submission})


@router.post("/{id}/submissions/{submissionId}/acknowledge")
async def acknowledge_submission_route(
    request: Request,
    id: str,
    submissionId: str,
    input_data: AcknowledgeSubmissionInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    submission = await acknowledge_submission(
        id,
        submissionId,
        _owner(principal),
        input_data,
        ip=ip,
        user_agent=user_agent,
    )
    return success("Report submission acknowledged", {"submission": submission})
