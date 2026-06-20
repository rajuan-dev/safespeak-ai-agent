from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.responses import success
from app.core.security import Principal, require_ai_consent
from app.models.ai import NarrativeInput, RedactInput, TranslateInput, TriageInput
from app.services.ai_tools import (
    clarifying_questions,
    extract_incident_fields,
    generate_summary,
    redact_pii,
    translate,
    triage_report,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/extract-incident-fields")
async def incident_fields(
    request: NarrativeInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success("Incident fields extracted", {"result": await extract_incident_fields(request)})


@router.post("/clarifying-questions")
async def questions(
    request: NarrativeInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "Clarifying questions generated",
        {"result": await clarifying_questions(request)},
    )


@router.post("/generate-summary")
async def summary(
    request: NarrativeInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success("Summary generated", {"result": await generate_summary(request)})


@router.post("/triage-report")
async def triage(
    request: TriageInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success("Triage report generated", {"result": await triage_report(request)})


@router.post("/translate")
async def translate_text(
    request: TranslateInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success("Translation generated", {"result": await translate(request)})


@router.post("/redact-pii")
async def redact(
    request: RedactInput,
    _principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success("PII redacted", {"result": redact_pii(request)})
