from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.responses import success
from app.core.security import (
    Principal,
    require_ai_consent,
    require_ai_or_transcription_consent,
)
from app.models.ai import (
    ClarifyingQuestionsInput,
    ExtractIncidentFieldsInput,
    GenerateSummaryInput,
    RedactInput,
    SynthesizeSpeechInput,
    TranscribeAudioInput,
    TranslateInput,
    TriageInput,
)
from app.services.ai_tools import (
    clarifying_questions,
    extract_incident_fields,
    generate_summary,
    redact_pii,
    synthesize_speech,
    transcribe_audio_file,
    translate,
    triage_report,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/extract-incident-fields")
async def incident_fields(
    request: ExtractIncidentFieldsInput,
    principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "Incident fields extracted",
        {"result": await extract_incident_fields(request, principal)},
        {"informationOnly": True},
    )


@router.post("/clarifying-questions")
async def questions(
    request: ClarifyingQuestionsInput,
    principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "Clarifying questions generated",
        {"result": await clarifying_questions(request, principal)},
        {"informationOnly": True},
    )


@router.post("/generate-summary")
async def summary(
    request: GenerateSummaryInput,
    principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "Summary generated",
        {"result": await generate_summary(request, principal)},
        {"informationOnly": True},
    )


@router.post("/triage-report")
async def triage(
    request: TriageInput,
    principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "Report triaged",
        {"result": await triage_report(request, principal)},
        {"informationOnly": True},
    )


@router.post("/translate")
async def translate_text(
    request: TranslateInput,
    principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "Text translated",
        {"result": await translate(request, principal)},
        {"informationOnly": True},
    )


@router.post("/redact-pii")
async def redact(
    request: RedactInput,
    principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "PII redacted",
        {"result": redact_pii(request, principal)},
        {"informationOnly": True},
    )


@router.post("/transcribe-audio")
async def transcribe_audio(
    principal: Annotated[Principal, Depends(require_ai_or_transcription_consent)],
    audio: UploadFile = File(...),
    reportId: str | None = Form(default=None),
    evidenceId: str | None = Form(default=None),
    language: str | None = Form(default=None),
    saveTranscript: bool | None = Form(default=None),
    useAsNarrative: bool | None = Form(default=None),
):
    request = TranscribeAudioInput(
        reportId=reportId,
        evidenceId=evidenceId,
        language=language,
        saveTranscript=saveTranscript,
        useAsNarrative=useAsNarrative,
    )
    file_bytes = await audio.read()
    result = await transcribe_audio_file(
        request,
        principal=principal,
        file_bytes=file_bytes,
        file_name=audio.filename or "audio-input.webm",
        mime_type=audio.content_type or "application/octet-stream",
    )
    return success("Audio transcribed successfully", result, {})


@router.post("/synthesize-speech")
async def synthesize(
    request: SynthesizeSpeechInput,
    principal: Annotated[Principal, Depends(require_ai_consent)],
):
    return success(
        "Speech synthesized successfully",
        await synthesize_speech(request, principal),
        {"informationOnly": True},
    )
