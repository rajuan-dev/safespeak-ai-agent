EVIDENCE_STATUS_PENDING_UPLOAD = "pending_upload"
EVIDENCE_STATUS_DRAFT = "draft"
EVIDENCE_STATUS_LOCAL_ONLY = "local_only"
EVIDENCE_STATUS_SYNCED = "synced"
EVIDENCE_STATUS_SYNC_FAILED = "sync_failed"
EVIDENCE_STATUS_DELETE_REQUESTED = "delete_requested"
EVIDENCE_STATUS_DELETED = "deleted"

EVIDENCE_STATUSES = {
    EVIDENCE_STATUS_PENDING_UPLOAD,
    EVIDENCE_STATUS_DRAFT,
    EVIDENCE_STATUS_LOCAL_ONLY,
    EVIDENCE_STATUS_SYNCED,
    EVIDENCE_STATUS_SYNC_FAILED,
    EVIDENCE_STATUS_DELETE_REQUESTED,
    EVIDENCE_STATUS_DELETED,
}

STORAGE_PROVIDER_LOCAL = "local_encrypted"
STORAGE_PROVIDER_S3 = "s3"

SUPPORTED_TRANSCRIPTION_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "video/mp4",
    "video/quicktime",
    "video/mpeg",
    "video/x-msvideo",
}
