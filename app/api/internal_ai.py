from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.responses import success
from app.core.security import Principal, require_internal_service
from app.models.ai import SynthesizeSpeechInput, TranscribeAudioInput
from app.models.internal_ai import (
    InternalCompletionInput,
    InternalEmbeddingInput,
    InternalVisionInput,
)
from app.services.ai_tools import synthesize_speech, transcribe_audio_file
from app.services.embeddings import embedding_service
from app.services.llm import llm_service

router = APIRouter(prefix="/internal/ai", tags=["internal-ai"])


@router.post("/complete")
async def complete(
    request: InternalCompletionInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    result = await llm_service.text_completion(
        system=request.systemPrompt,
        user=request.userPrompt,
        temperature=request.temperature,
        model=request.model,
    )
    return success("AI completion generated", {"text": result})


@router.post("/complete-json")
async def complete_json(
    request: InternalCompletionInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    result = await llm_service.json_completion(
        system=request.systemPrompt,
        user=request.userPrompt,
        fallback={},
        temperature=request.temperature,
        model=request.model,
    )
    return success("AI JSON completion generated", {"result": result})


@router.post("/embeddings")
async def embeddings(
    request: InternalEmbeddingInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    vectors = await embedding_service.embed(request.texts, model=request.model)
    return success("Embeddings generated", {"embeddings": vectors})


@router.post("/transcribe")
async def transcribe(
    _authorized: Annotated[None, Depends(require_internal_service)],
    audio: Annotated[UploadFile, File(...)],
    language: Annotated[str | None, Form()] = None,
):
    result = await transcribe_audio_file(
        TranscribeAudioInput(language=language, saveTranscript=False, useAsNarrative=False),
        principal=Principal(actor_type="internal"),
        file_bytes=await audio.read(),
        file_name=audio.filename or "audio-input.webm",
        mime_type=audio.content_type or "application/octet-stream",
    )
    return success("Audio transcribed", result)


@router.post("/synthesize")
async def synthesize(
    request: SynthesizeSpeechInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    return success("Speech synthesized", await synthesize_speech(request))


@router.post("/vision-text")
async def vision_text(
    request: InternalVisionInput,
    _authorized: Annotated[None, Depends(require_internal_service)],
):
    text = await llm_service.vision_text_completion(
        instruction=request.instruction,
        image_data=request.imageData,
        model=request.model,
    )
    return success("Vision text extracted", {"text": text})
