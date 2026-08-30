from app.core.config import get_settings
from app.modules.ai.repository import get_ai_repository
from app.modules.ai.service import (
    clarifying_questions as _clarifying_questions,
)
from app.modules.ai.service import (
    extract_incident_fields as _extract_incident_fields,
)
from app.modules.ai.service import (
    generate_summary as _generate_summary,
)
from app.modules.ai.service import (
    httpx,
    llm_service,
)
from app.modules.ai.service import (
    redact_pii as _redact_pii,
)
from app.modules.ai.service import (
    synthesize_speech as _synthesize_speech,
)
from app.modules.ai.service import (
    transcribe_audio_file as _transcribe_audio_file,
)
from app.modules.ai.service import (
    translate as _translate,
)
from app.modules.ai.service import (
    triage_report as _triage_report,
)


async def _get_public_platform_settings():
    return await get_ai_repository().get_public_platform_settings()


async def extract_incident_fields(request, principal=None):
    return await _extract_incident_fields(
        request,
        principal,
        repository=get_ai_repository(),
        llm=llm_service,
    )


async def clarifying_questions(request, principal=None):
    return await _clarifying_questions(
        request,
        principal,
        repository=get_ai_repository(),
        llm=llm_service,
    )


async def generate_summary(request, principal=None):
    return await _generate_summary(
        request,
        principal,
        repository=get_ai_repository(),
        llm=llm_service,
    )


async def triage_report(request, principal=None):
    return await _triage_report(
        request,
        principal,
        repository=get_ai_repository(),
        llm=llm_service,
        platform_settings=await _get_public_platform_settings(),
    )


async def translate(request, principal=None):
    return await _translate(
        request,
        principal,
        repository=get_ai_repository(),
        llm=llm_service,
    )


def redact_pii(request, principal=None):
    return _redact_pii(request, principal, repository=get_ai_repository())


async def transcribe_audio_file(request, *, principal, file_bytes, file_name, mime_type):
    return await _transcribe_audio_file(
        request,
        principal=principal,
        file_bytes=file_bytes,
        file_name=file_name,
        mime_type=mime_type,
        repository=get_ai_repository(),
        http_client_factory=lambda timeout: httpx.AsyncClient(timeout=timeout),
        settings_factory=get_settings,
    )


async def synthesize_speech(request, principal=None):
    return await _synthesize_speech(
        request,
        principal,
        repository=get_ai_repository(),
        http_client_factory=lambda timeout: httpx.AsyncClient(timeout=timeout),
        settings_factory=get_settings,
    )
