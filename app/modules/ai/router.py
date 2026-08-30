from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.core.responses import success

from .dependencies import CurrentAiOrTranscriptionPrincipal, CurrentAiPrincipal
from .schema import (
    ClarifyingQuestionsInput,
    ExtractIncidentFieldsInput,
    GenerateSummaryInput,
    RedactInput,
    SynthesizeSpeechInput,
    TranscribeAudioInput,
    TranslateInput,
    TriageInput,
)
from .service import (
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
    principal: CurrentAiPrincipal,
):
    return success(
        "Incident fields extracted",
        {"result": await extract_incident_fields(request, principal)},
        {"informationOnly": True},
    )


@router.post("/clarifying-questions")
async def questions(
    request: ClarifyingQuestionsInput,
    principal: CurrentAiPrincipal,
):
    return success(
        "Clarifying questions generated",
        {"result": await clarifying_questions(request, principal)},
        {"informationOnly": True},
    )


@router.post("/generate-summary")
async def summary(
    request: GenerateSummaryInput,
    principal: CurrentAiPrincipal,
):
    return success(
        "Summary generated",
        {"result": await generate_summary(request, principal)},
        {"informationOnly": True},
    )


@router.post("/triage-report")
async def triage(
    request: TriageInput,
    principal: CurrentAiPrincipal,
):
    return success(
        "Report triaged",
        {"result": await triage_report(request, principal)},
        {"informationOnly": True},
    )


@router.post("/translate")
async def translate_text(
    request: TranslateInput,
    principal: CurrentAiPrincipal,
):
    return success(
        "Text translated",
        {"result": await translate(request, principal)},
        {"informationOnly": True},
    )


@router.post("/redact-pii")
async def redact(
    request: RedactInput,
    principal: CurrentAiPrincipal,
):
    return success(
        "PII redacted",
        {"result": redact_pii(request, principal)},
        {"informationOnly": True},
    )


@router.post("/transcribe-audio")
async def transcribe_audio(
    principal: CurrentAiOrTranscriptionPrincipal,
    audio: Annotated[UploadFile, File(...)],
    reportId: Annotated[str | None, Form()] = None,
    evidenceId: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    saveTranscript: Annotated[bool | None, Form()] = None,
    useAsNarrative: Annotated[bool | None, Form()] = None,
):
    request = TranscribeAudioInput(
        reportId=reportId,
        evidenceId=evidenceId,
        language=language,
        saveTranscript=saveTranscript,
        useAsNarrative=useAsNarrative,
    )
    result = await transcribe_audio_file(
        request,
        principal=principal,
        file_bytes=await audio.read(),
        file_name=audio.filename or "audio-input.webm",
        mime_type=audio.content_type or "application/octet-stream",
    )
    return success("Audio transcribed successfully", result, {})


@router.post("/synthesize-speech")
async def synthesize(
    request: SynthesizeSpeechInput,
    principal: CurrentAiPrincipal,
):
    return success(
        "Speech synthesized successfully",
        await synthesize_speech(request, principal),
        {"informationOnly": True},
    )
