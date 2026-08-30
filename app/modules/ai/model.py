AI_ACTIONS = {
    "extractIncidentFields": "ai.extract_incident_fields",
    "triageReport": "ai.triage_report",
    "clarifyingQuestions": "ai.clarifying_questions",
    "generateSummary": "ai.generate_summary",
    "translate": "ai.translate",
    "redactPii": "ai.redact_pii",
    "transcribeAudio": "ai.audio_transcription_requested",
    "synthesizeSpeech": "ai.speech_synthesis_requested",
    "conversationResponse": "ai.conversation_response",
}

AI_REVIEW_STATUSES = {
    "pendingHumanReview": "pending_human_review",
    "approved": "approved",
    "rejected": "rejected",
    "automatedReviewRequired": "automated_review_required",
    "conversationSupport": "conversation_support",
}

DEFAULT_AI_LANGUAGE = "en"

SAFE_SPEAK_INFORMATION_ONLY_DISCLAIMER = (
    "This is general information only, not legal advice. For personal legal help, "
    "contact a qualified lawyer, Legal Aid, or a relevant support service."
)
