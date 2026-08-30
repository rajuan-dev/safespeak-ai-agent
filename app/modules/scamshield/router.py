from fastapi import APIRouter, File, Form, Request, UploadFile, status

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import (
    AnalyzeEmailInput,
    AnalyzeScreenshotInput,
    AnalyzeTextInput,
    CheckUrlInput,
    GenerateReportDraftByIdInput,
    GenerateReportDraftInput,
    RedactScamContentInput,
    SubmitScamReportByIdInput,
    SubmitScamReportInput,
    parse_metadata_form,
)
from .service import (
    analyze_email,
    analyze_screenshot,
    analyze_text,
    check_url,
    generate_report_draft,
    get_analysis_by_id,
    redact_scam_content,
    submit_scam_report,
)

router = APIRouter(prefix="/scamshield", tags=["scamshield"])
FILES_FORM = File(default=None)


def _context(request: Request, principal: AuthenticatedSessionOrUser) -> dict:
    return {
        "owner": {"userId": principal.user_id, "sessionId": principal.session_id},
        "ip": request.client.host if request.client else None,
        "userAgent": request.headers.get("user-agent"),
    }


@router.post("/analyze-text", status_code=status.HTTP_201_CREATED)
async def analyze_text_route(
    request: Request,
    input_data: AnalyzeTextInput,
    principal: AuthenticatedSessionOrUser,
):
    analysis = await analyze_text(_context(request, principal), input_data)
    return success("ScamShield text analysis completed", {"analysis": analysis})


@router.post("/analyze-email", status_code=status.HTTP_201_CREATED)
async def analyze_email_route(
    request: Request,
    input_data: AnalyzeEmailInput,
    principal: AuthenticatedSessionOrUser,
):
    analysis = await analyze_email(_context(request, principal), input_data)
    return success("ScamShield email analysis completed", {"analysis": analysis})


@router.post("/analyze-screenshot", status_code=status.HTTP_201_CREATED)
async def analyze_screenshot_route(
    request: Request,
    principal: AuthenticatedSessionOrUser,
    imageText: str | None = Form(default=None),
    imageBase64: str | None = Form(default=None),
    mimeType: str | None = Form(default=None),
    evidenceId: str | None = Form(default=None),
    reportId: str | None = Form(default=None),
    metadata: str | None = Form(default=None),
    files: list[UploadFile] | None = FILES_FORM,
):
    input_data = AnalyzeScreenshotInput(
        imageText=imageText,
        imageBase64=imageBase64,
        mimeType=mimeType,
        evidenceId=evidenceId,
        reportId=reportId,
        metadata=parse_metadata_form(metadata),
    )
    analysis = await analyze_screenshot(_context(request, principal), input_data, files=files)
    return success("ScamShield screenshot analysis completed", {"analysis": analysis})


@router.post("/check-url", status_code=status.HTTP_201_CREATED)
async def check_url_route(
    request: Request,
    input_data: CheckUrlInput,
    principal: AuthenticatedSessionOrUser,
):
    analysis = await check_url(_context(request, principal), input_data)
    return success("ScamShield URL check completed", {"analysis": analysis})


@router.get("/{id}")
async def get_analysis_route(request: Request, id: str, principal: AuthenticatedSessionOrUser):
    analysis = await get_analysis_by_id(_context(request, principal), id)
    return success("ScamShield analysis retrieved", {"analysis": analysis})


@router.post("/redact")
async def redact_content_route(
    request: Request,
    input_data: RedactScamContentInput,
    principal: AuthenticatedSessionOrUser,
):
    result = await redact_scam_content(_context(request, principal), input_data)
    return success("ScamShield content redacted", {"result": result})


@router.post("/generate-report-draft")
async def generate_report_draft_route(
    request: Request,
    input_data: GenerateReportDraftInput,
    principal: AuthenticatedSessionOrUser,
):
    analysis = await generate_report_draft(_context(request, principal), input_data)
    return success("ScamShield report draft generated", {"analysis": analysis})


@router.post("/{id}/generate-report-draft")
async def generate_report_draft_by_id_route(
    request: Request,
    id: str,
    input_data: GenerateReportDraftByIdInput,
    principal: AuthenticatedSessionOrUser,
):
    analysis = await generate_report_draft(
        _context(request, principal),
        GenerateReportDraftInput(
            analysisId=id,
            notes=input_data.notes,
            autoRedactPII=input_data.auto_redact_pii,
            redactionMode=input_data.redaction_mode,
        ),
    )
    return success("ScamShield report draft generated", {"analysis": analysis})


@router.post("/submit")
async def submit_route(
    request: Request,
    input_data: SubmitScamReportInput,
    principal: AuthenticatedSessionOrUser,
):
    analysis = await submit_scam_report(_context(request, principal), input_data)
    return success("ScamShield report submitted", {"analysis": analysis})


@router.post("/{id}/submit")
async def submit_by_id_route(
    request: Request,
    id: str,
    input_data: SubmitScamReportByIdInput,
    principal: AuthenticatedSessionOrUser,
):
    analysis = await submit_scam_report(
        _context(request, principal),
        SubmitScamReportInput(
            analysisId=id,
            destination=input_data.destination,
            consentToShare=input_data.consent_to_share,
        ),
    )
    return success("ScamShield report submitted", {"analysis": analysis})
