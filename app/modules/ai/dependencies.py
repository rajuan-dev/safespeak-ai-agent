from typing import Annotated

from fastapi import Depends

from app.core.security import (
    Principal,
    require_ai_consent,
    require_ai_or_transcription_consent,
)

CurrentAiPrincipal = Annotated[Principal, Depends(require_ai_consent)]
CurrentAiOrTranscriptionPrincipal = Annotated[
    Principal, Depends(require_ai_or_transcription_consent)
]

__all__ = [
    "CurrentAiOrTranscriptionPrincipal",
    "CurrentAiPrincipal",
    "Principal",
    "require_ai_consent",
    "require_ai_or_transcription_consent",
]
