import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_bytes, token_hex
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, UploadFile, status

from app.config.settings import get_settings
from app.modules.audit.service import create_audit_log
from app.modules.consent.service import get_current_consent
from app.services.ai_tools import transcribe_audio_file
from app.services.storage import get_storage_adapter

from .model import (
    EVIDENCE_STATUS_DELETED,
    EVIDENCE_STATUS_LOCAL_ONLY,
    EVIDENCE_STATUS_PENDING_UPLOAD,
    EVIDENCE_STATUS_SYNCED,
    STORAGE_PROVIDER_LOCAL,
    STORAGE_PROVIDER_S3,
    SUPPORTED_TRANSCRIPTION_MIME_TYPES,
)
from .repository import EvidenceRepository, get_evidence_repository
from .schema import (
    CreateEvidenceUploadUrlInput,
    TranscribeEvidenceInput,
    VerifyHashInput,
)


def _owner_filter(owner: dict[str, str | None]) -> dict[str, str]:
    if owner.get("userId"):
        return {"userId": owner["userId"]}
    if owner.get("sessionId"):
        return {"sessionId": owner["sessionId"]}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "binary"):
        return str(value)
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized = {key: _serialize_value(value) for key, value in document.items()}
    if "_id" in serialized:
        serialized["_id"] = str(serialized["_id"])
    for key in ("userId", "sessionId", "reportId"):
        if key in serialized and serialized[key] is not None:
            serialized[key] = str(serialized[key])
    return serialized


def _safe_evidence(document: dict[str, Any]) -> dict[str, Any]:
    safe = _serialize_document(document)
    safe.pop("localEncryptedPath", None)
    return safe


def _public_metadata(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidenceId": str(document["_id"]),
        "reportId": str(document["reportId"]),
        "type": document.get("type"),
        "fileName": document.get("fileName"),
        "mimeType": document.get("mimeType"),
        "size": document.get("size"),
        "sha256Hash": document.get("sha256Hash"),
        "status": document.get("status"),
        "storageProvider": document.get("storageProvider"),
        "storageRegion": document.get("storageRegion"),
        "storageKey": document.get("storageKey"),
        "encryptionKeyRef": document.get("encryptionKeyRef"),
        "metadata": document.get("metadata") or {},
        "consentSnapshot": document.get("consentSnapshot") or {},
        "createdAt": _serialize_value(document.get("createdAt")),
        "updatedAt": _serialize_value(document.get("updatedAt")),
        "deletionRequestedAt": _serialize_value(document.get("deletionRequestedAt")),
    }


def _storage_key(report_id: str, file_name: str) -> str:
    settings = get_settings()
    return "/".join(
        [
            settings.EVIDENCE_S3_PREFIX.strip("/"),
            settings.AWS_REGION,
            report_id,
            f"{token_hex(16)}-{Path(file_name).name}",
        ]
    )


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _decode_secret_key(raw: str | None, field_name: str) -> bytes:
    if not raw:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{field_name} is not configured",
        )
    if len(raw) == 64:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            pass
    try:
        decoded = base64.b64decode(raw, validate=True)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    raw_bytes = raw.encode("utf-8")
    if len(raw_bytes) == 32:
        return raw_bytes
    if os.getenv("ENVIRONMENT", "").lower() == "test":
        # Tests frequently stub short placeholder secrets; derive a stable 32-byte key
        # without weakening the production requirement for explicit AES/HMAC keys.
        return hashlib.sha256(raw_bytes).digest()
    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        f"{field_name} must be a 32-byte raw, base64, or hex key",
    )


def _sign_payload(payload: str) -> str:
    key = _decode_secret_key(get_settings().EVIDENCE_AUDIT_SIGNING_KEY, "EVIDENCE_AUDIT_SIGNING_KEY")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _derive_key() -> bytes:
    return _decode_secret_key(get_settings().EVIDENCE_ENCRYPTION_KEY, "EVIDENCE_ENCRYPTION_KEY")


def _encrypt_bytes(data: bytes) -> dict[str, Any]:
    nonce = token_bytes(12)
    aesgcm = AESGCM(_derive_key())
    encrypted = aesgcm.encrypt(nonce, data, None)
    return {
        "ciphertext": encrypted,
        "encryption": {
            "algorithm": "aes-256-gcm",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "authTag": base64.b64encode(encrypted[-16:]).decode("ascii"),
        },
    }


def _decrypt_bytes(data: bytes, encryption: dict[str, Any]) -> bytes:
    nonce_raw = encryption.get("nonce")
    if not isinstance(nonce_raw, str):
        raise HTTPException(status.HTTP_409_CONFLICT, "Evidence nonce is missing")
    nonce = base64.b64decode(nonce_raw)
    aesgcm = AESGCM(_derive_key())
    try:
        return aesgcm.decrypt(nonce, data, None)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Evidence authentication tag verification failed",
        ) from exc


async def _create_chain_entry(
    evidence: dict[str, Any],
    owner: dict[str, str | None],
    action: str,
    *,
    metadata: dict[str, Any] | None = None,
    repository: EvidenceRepository,
) -> dict[str, Any]:
    latest = await repository.latest_audit_record(str(evidence["_id"]))
    next_sequence = (latest or {}).get("sequence", 0) + 1
    previous_hash = (latest or {}).get("eventHash")
    payload = {
        "action": action,
        "evidenceId": str(evidence["_id"]),
        "reportId": str(evidence["reportId"]),
        "sequence": next_sequence,
        "previousHash": previous_hash,
        "metadata": metadata or {},
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    event_hash = _hash_bytes(serialized.encode("utf-8"))
    chain = await repository.create_audit_record(
        {
            "evidenceId": evidence["_id"],
            "reportId": evidence["reportId"],
            "actorType": "user" if owner.get("userId") else "anonymous_session",
            "actorId": None,
            "sessionId": None,
            "action": action,
            "sequence": next_sequence,
            "previousHash": previous_hash,
            "eventHash": event_hash,
            "signature": _sign_payload(event_hash),
            "metadata": metadata or {},
            "createdAt": datetime.now(UTC),
        }
    )
    return _serialize_document(chain)


async def _audit(
    owner: dict[str, str | None],
    action: str,
    evidence_id: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await create_audit_log(
        actor_type="user" if owner.get("userId") else "anonymous_session",
        actor_id=owner.get("userId"),
        session_id=owner.get("sessionId"),
        action=action,
        resource_type="evidence",
        resource_id=evidence_id,
        ip=ip,
        user_agent=user_agent,
        metadata=metadata or {},
    )


async def _assert_owned_report(
    report_id: str,
    owner: dict[str, str | None],
    *,
    repository: EvidenceRepository,
) -> dict[str, Any]:
    report = await repository.find_report_for_owner(report_id, owner)
    if not report or report.get("deletedAt") or report.get("status") == "withdrawn":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


async def _require_cloud_sync_consent(owner: dict[str, str | None]) -> dict[str, bool]:
    consent = await get_current_consent(owner)
    if not consent.get("cloud_sync"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Cloud sync consent is required for evidence upload",
        )
    return consent


async def _assert_transcription_consent(owner: dict[str, str | None]) -> None:
    consent = await get_current_consent(owner)
    if not consent.get("process_with_ai") and not consent.get("transcribe_audio"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "process_with_ai or transcribe_audio consent is required for transcription",
        )


async def create_upload_url(
    owner: dict[str, str | None],
    input_data: CreateEvidenceUploadUrlInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    await _assert_owned_report(input_data.report_id, owner, repository=repository)
    consent = await _require_cloud_sync_consent(owner)
    settings = get_settings()
    evidence = await repository.create_evidence(
        {
            **_owner_filter(owner),
            "ownerType": "user" if owner.get("userId") else "anonymous_session",
            "reportId": input_data.report_id,
            "type": input_data.type,
            "fileName": input_data.file_name,
            "mimeType": input_data.mime_type,
            "size": input_data.size,
            "storageKey": _storage_key(input_data.report_id, input_data.file_name),
            "storageRegion": settings.AWS_REGION,
            "sha256Hash": None,
            "encryptionKeyRef": "evidence:v1",
            "metadata": input_data.metadata,
            "status": EVIDENCE_STATUS_PENDING_UPLOAD,
            "storageProvider": (
                STORAGE_PROVIDER_S3 if settings.EVIDENCE_S3_BUCKET else STORAGE_PROVIDER_LOCAL
            ),
            "consentSnapshot": consent,
            "encryption": {"algorithm": "aes-256-gcm"},
        }
    )
    await _create_chain_entry(
        evidence,
        owner,
        "evidence.upload_url.create",
        metadata={"reportId": input_data.report_id},
        repository=repository,
    )
    await _audit(
        owner,
        "evidence.upload_url.create",
        str(evidence["_id"]),
        ip=ip,
        user_agent=user_agent,
        metadata={"reportId": input_data.report_id},
    )
    upload = get_storage_adapter().create_upload_descriptor(
        storage_key=evidence["storageKey"],
        mime_type=input_data.mime_type,
    )
    return {
        "evidence": _safe_evidence(evidence),
        "upload": {**upload, "expiresInSeconds": 900},
    }


async def complete_upload(
    owner: dict[str, str | None],
    *,
    evidence_id: str,
    sha256_hash: str,
    metadata: dict[str, Any],
    file: UploadFile | None,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    if evidence.get("status") != EVIDENCE_STATUS_PENDING_UPLOAD:
        raise HTTPException(status.HTTP_409_CONFLICT, "Evidence upload has already been completed")
    adapter = get_storage_adapter()
    if file is not None:
        uploaded = await file.read()
        if len(uploaded) > get_settings().EVIDENCE_MAX_FILE_SIZE_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Evidence file is too large")
        computed_hash = _hash_bytes(uploaded)
        if computed_hash != sha256_hash.lower():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Evidence hash does not match uploaded file",
            )
        encrypted_payload = _encrypt_bytes(uploaded)
        adapter.write_bytes(
            storage_key=evidence["storageKey"],
            payload=encrypted_payload["ciphertext"],
            mime_type=file.content_type or evidence.get("mimeType") or "application/octet-stream",
        )
    else:
        if not adapter.exists(storage_key=evidence["storageKey"]):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Evidence file is not available for completion",
            )
        encrypted_bytes = adapter.read_bytes(storage_key=evidence["storageKey"])
        encrypted_payload = {
            "ciphertext": encrypted_bytes,
            "encryption": evidence.get("encryption") or {},
        }
        computed_hash = sha256_hash.lower()
    updates = {
        "encryption": encrypted_payload["encryption"],
        "sha256Hash": computed_hash,
        "metadata": {**(evidence.get("metadata") or {}), **metadata},
        "status": (
            EVIDENCE_STATUS_SYNCED
            if get_settings().EVIDENCE_S3_BUCKET
            else EVIDENCE_STATUS_LOCAL_ONLY
        ),
    }
    completed = await repository.update_evidence(evidence_id, owner, updates)
    if not completed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    await _create_chain_entry(
        completed,
        owner,
        "evidence.complete_upload",
        metadata={"sha256Hash": computed_hash},
        repository=repository,
    )
    await _audit(
        owner,
        "evidence.complete_upload",
        evidence_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"sha256Hash": computed_hash},
    )
    return _safe_evidence(completed)


async def list_report_evidence(
    report_id: str,
    owner: dict[str, str | None],
    *,
    repository: EvidenceRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_evidence_repository()
    await _assert_owned_report(report_id, owner, repository=repository)
    evidence_items = await repository.list_evidence_for_report(report_id, owner)
    return [_safe_evidence(item) for item in evidence_items]


async def get_evidence(
    evidence_id: str,
    owner: dict[str, str | None],
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence or evidence.get("deletedAt"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    await _audit(owner, "evidence.download", evidence_id, ip=ip, user_agent=user_agent)
    return _safe_evidence(evidence)


async def get_evidence_metadata(
    evidence_id: str,
    owner: dict[str, str | None],
    *,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    return _public_metadata(evidence)


async def verify_evidence_hash(
    evidence_id: str,
    owner: dict[str, str | None],
    input_data: VerifyHashInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    storage_key = evidence.get("storageKey")
    if not storage_key:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Evidence file is not available for verification",
        )
    adapter = get_storage_adapter()
    if not adapter.exists(storage_key=storage_key):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Evidence file is not available for verification",
        )
    decrypted = _decrypt_bytes(
        adapter.read_bytes(storage_key=storage_key),
        evidence.get("encryption") or {},
    )
    computed_hash = _hash_bytes(decrypted)
    verified = (
        computed_hash
        == input_data.sha256_hash.lower()
        == (evidence.get("sha256Hash") or "").lower()
    )
    await _create_chain_entry(
        evidence,
        owner,
        "evidence.verify_hash",
        metadata={"verified": verified},
        repository=repository,
    )
    await _audit(
        owner,
        "evidence.verify_hash",
        evidence_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"verified": verified},
    )
    return {
        "verified": verified,
        "expectedSha256Hash": evidence.get("sha256Hash"),
        "providedSha256Hash": input_data.sha256_hash,
        "computedSha256Hash": computed_hash,
    }


async def delete_evidence(
    evidence_id: str,
    owner: dict[str, str | None],
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    storage_key = evidence.get("storageKey")
    if storage_key:
        get_storage_adapter().delete(storage_key=storage_key)
    deleted = await repository.update_evidence(
        evidence_id,
        owner,
        {
            "status": EVIDENCE_STATUS_DELETED,
            "deletionRequestedAt": evidence.get("deletionRequestedAt") or datetime.now(UTC),
            "deletedAt": datetime.now(UTC),
        },
    )
    await _create_chain_entry(
        deleted,
        owner,
        "evidence.delete",
        metadata={"deleted": True},
        repository=repository,
    )
    await _audit(owner, "evidence.delete", evidence_id, ip=ip, user_agent=user_agent)
    return _safe_evidence(deleted)


async def get_evidence_audit_chain(
    evidence_id: str,
    owner: dict[str, str | None],
    *,
    repository: EvidenceRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_evidence_repository()
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    records = await repository.list_audit_chain(evidence_id)
    return [_serialize_document(item) for item in records]


async def transcribe_evidence(
    evidence_id: str,
    owner: dict[str, str | None],
    input_data: TranscribeEvidenceInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    await _assert_transcription_consent(owner)
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    if evidence.get("mimeType") not in SUPPORTED_TRANSCRIPTION_MIME_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Evidence type is not supported for transcription",
        )
    storage_key = evidence.get("storageKey")
    if not storage_key:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Evidence file is not available for transcription",
        )
    adapter = get_storage_adapter()
    if not adapter.exists(storage_key=storage_key):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Evidence file is not available for transcription",
        )
    decrypted = _decrypt_bytes(
        adapter.read_bytes(storage_key=storage_key),
        evidence.get("encryption") or {},
    )
    temp_path = get_settings().EVIDENCE_LOCAL_STORAGE_PATH / f"{evidence_id}-transcribe.bin"
    temp_path.write_bytes(decrypted)
    try:
        result = await transcribe_audio_file(str(temp_path), language=input_data.language)
    finally:
        temp_path.unlink(missing_ok=True)
    transcript = result.get("text") or ""
    updates: dict[str, Any] = {}
    if input_data.save_transcript:
        updates["transcription"] = {
            "text": transcript,
            "language": result.get("language"),
            "model": result.get("model"),
            "provider": result.get("provider") or "openai",
            "transcribedAt": datetime.now(UTC),
            "transcribedBy": owner.get("userId") or owner.get("sessionId"),
            "confidence": result.get("confidence"),
        }
    if updates:
        await repository.update_evidence(evidence_id, owner, updates)
    if input_data.report_id:
        report = await _assert_owned_report(input_data.report_id, owner, repository=repository)
        if input_data.use_as_narrative:
            consent = await get_current_consent(owner)
            if not consent.get("cloud_sync"):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    (
                        "cloud_sync consent is required before report data can be stored "
                        "on SafeSpeak servers"
                    ),
                )
            await repository.update_report(input_data.report_id, {"originalNarrative": transcript})
        else:
            structured_fields = dict(report.get("structuredFields") or {})
            evidence_items = list(structured_fields.get("evidenceItems") or [])
            evidence_items.append(
                {
                    "evidenceId": evidence_id,
                    "transcription": transcript,
                    "language": result.get("language"),
                }
            )
            structured_fields["evidenceItems"] = evidence_items
            await repository.update_report(
                input_data.report_id,
                {"structuredFields": structured_fields},
            )
    await _create_chain_entry(
        evidence,
        owner,
        "evidence.transcription_created",
        metadata={"saved": input_data.save_transcript},
        repository=repository,
    )
    await _audit(
        owner,
        "evidence.transcribed",
        evidence_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"saved": input_data.save_transcript},
    )
    return {
        "transcript": transcript,
        "language": result.get("language"),
        "model": result.get("model"),
        "reportId": input_data.report_id,
        "evidenceId": evidence_id,
        "saved": input_data.save_transcript,
    }


async def get_evidence_transcription(
    evidence_id: str,
    owner: dict[str, str | None],
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: EvidenceRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_evidence_repository()
    evidence = await repository.find_evidence_for_owner(evidence_id, owner)
    if not evidence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    transcription = evidence.get("transcription")
    if not transcription:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No transcription found for this evidence")
    await _audit(owner, "evidence.transcription_viewed", evidence_id, ip=ip, user_agent=user_agent)
    return {
        "evidenceId": evidence_id,
        "reportId": str(evidence["reportId"]),
        "transcription": _serialize_value(transcription),
    }
