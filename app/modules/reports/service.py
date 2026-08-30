import json
from datetime import UTC, datetime
from secrets import token_hex
from typing import Any

from fastapi import HTTPException, status

from app.config.settings import get_settings
from app.modules.audit.service import create_audit_log
from app.modules.consent.service import get_current_consent

from .model import (
    ACTIVE_SUBMISSION_STATUSES,
    REPORT_STATUS_DELETED,
    REPORT_STATUS_DRAFT,
    REPORT_STATUS_INFO_ONLY,
    REPORT_STATUS_PENDING_SUBMISSION,
    REPORT_STATUS_READY_FOR_REVIEW,
    REPORT_STATUS_RECEIVED,
    REPORT_STATUS_SUBMITTED,
    REPORT_STATUS_WITHDRAWN,
    SUBMISSION_STATUS_ACKNOWLEDGED,
    SUBMISSION_STATUS_CONFIG_MISSING,
    SUBMISSION_STATUS_REQUIRES_MANUAL_ACTION,
    SUBMISSION_STATUS_SUBMITTED,
    WITHDRAW_BLOCKED_STATUSES,
)
from .repository import ReportsRepository, get_reports_repository
from .schema import (
    AcknowledgeSubmissionInput,
    CreateReportInput,
    CreateSubmissionInput,
    MarkInfoOnlyInput,
    RequestDeleteInput,
    SubmissionPreviewInput,
    UpdateReportInput,
    WithdrawReportInput,
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
    for key in ("userId", "sessionId", "reportId", "destinationId"):
        if key in serialized and serialized[key] is not None:
            serialized[key] = str(serialized[key])
    return serialized


def _normalize_report_defaults(
    payload: dict[str, Any],
    *,
    profile: dict[str, Any] | None,
    anonymous_session: dict[str, Any] | None,
) -> dict[str, Any]:
    if not payload.get("language"):
        payload["language"] = (
            (profile or {}).get("preferredLanguage")
            or (anonymous_session or {}).get("language")
            or "en"
        )
    if not payload.get("jurisdiction"):
        payload["jurisdiction"] = (
            (profile or {}).get("jurisdiction")
            or (anonymous_session or {}).get("jurisdiction")
            or "NSW"
        )
    payload.setdefault("status", REPORT_STATUS_DRAFT)
    payload.setdefault("structuredFields", {})
    return payload


def _generate_ref_no(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"SSR-{now.strftime('%Y%m%d')}-{token_hex(4).upper()}"


def _build_history(status_value: str, reason: str) -> dict[str, Any]:
    return {"status": status_value, "reason": reason, "changedAt": datetime.now(UTC)}


async def _require_cloud_sync_consent(owner: dict[str, str | None]) -> dict[str, bool]:
    consent = await get_current_consent(owner)
    if not consent.get("cloud_sync"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "cloud_sync consent is required before report data can be stored on SafeSpeak servers",
        )
    return consent


async def _audit(
    owner: dict[str, str | None],
    action: str,
    resource_type: str,
    resource_id: str,
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
        resource_type=resource_type,
        resource_id=resource_id,
        ip=ip,
        user_agent=user_agent,
        metadata=metadata or {},
    )


def _missing_required_fields(report: dict[str, Any], evidence_count: int) -> list[str]:
    missing: list[str] = []
    if not report.get("originalNarrative"):
        missing.append("originalNarrative")
    if not report.get("incidentType"):
        missing.append("incidentType")
    if not report.get("severity"):
        missing.append("severity")
    if not evidence_count:
        missing.append("evidence")
    return missing


def _get_required_consent_flags(destination: dict[str, Any]) -> list[str]:
    metadata = destination.get("metadata") or {}
    flags = metadata.get("requiredConsentFlags") or []
    if destination.get("consentRequired") and not flags:
        return ["share_with_agencies"]
    return list(flags)


def _build_destination_preview(
    report: dict[str, Any],
    destination: dict[str, Any],
    template: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    consent: dict[str, bool],
    anonymity_mode: str,
    notes: str | None = None,
) -> dict[str, Any]:
    missing_required_info = _missing_required_fields(report, len(evidence))
    required_consent_flags = _get_required_consent_flags(destination)
    missing_consent_flags = [flag for flag in required_consent_flags if not consent.get(flag)]
    delivery_status = _delivery_readiness(destination)
    payload = {
        "reportRefNo": report.get("refNo"),
        "anonymityMode": anonymity_mode,
        "destinationName": destination.get("name"),
        "notes": notes,
        "language": report.get("language"),
        "jurisdiction": report.get("jurisdiction"),
        "narrative": report.get("originalNarrative"),
        "structuredFields": report.get("structuredFields") or {},
    }
    return {
        "destination": _serialize_document(destination),
        "template": _serialize_document(template) if template else None,
        "missingRequiredInfo": missing_required_info,
        "missingMappedFields": [],
        "requiredConsentFlags": required_consent_flags,
        "missingConsentFlags": missing_consent_flags,
        "deliveryReadiness": delivery_status,
        "payload": payload,
        "evidence": [
            {
                "id": str(item.get("_id")),
                "type": item.get("type"),
                "fileName": item.get("fileName"),
                "mimeType": item.get("mimeType"),
                "size": item.get("size"),
            }
            for item in evidence
        ],
    }


def _delivery_readiness(destination: dict[str, Any]) -> dict[str, Any]:
    channel = destination.get("channel") or "manual_export_json"
    settings = get_settings()
    if channel in {"manual_export_pdf", "manual_export_json", "booking_link"}:
        return {"status": SUBMISSION_STATUS_REQUIRES_MANUAL_ACTION, "issues": []}
    if channel == "secure_email":
        if not settings.DELIVERY_EMAIL_WEBHOOK_URL or not settings.DELIVERY_EMAIL_WEBHOOK_TOKEN:
            return {
                "status": SUBMISSION_STATUS_CONFIG_MISSING,
                "issues": ["DELIVERY_EMAIL_WEBHOOK_URL", "DELIVERY_EMAIL_WEBHOOK_TOKEN"],
            }
        return {"status": SUBMISSION_STATUS_SUBMITTED, "issues": []}
    if channel in {"api_oauth", "api_mtls"}:
        missing = []
        if channel == "api_oauth" and not settings.DELIVERY_API_BEARER_TOKEN:
            missing.append("DELIVERY_API_BEARER_TOKEN")
        if channel == "api_mtls" and not settings.DELIVERY_MTLS_PROXY_URL:
            missing.append("DELIVERY_MTLS_PROXY_URL")
        if missing:
            return {"status": SUBMISSION_STATUS_CONFIG_MISSING, "issues": missing}
        return {"status": SUBMISSION_STATUS_SUBMITTED, "issues": []}
    return {"status": SUBMISSION_STATUS_REQUIRES_MANUAL_ACTION, "issues": []}


async def create_report(
    owner: dict[str, str | None],
    input_data: CreateReportInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    consent = await _require_cloud_sync_consent(owner)
    profile = await repository.get_profile(owner)
    anonymous_session = await repository.get_anonymous_session(owner.get("sessionId"))
    payload = _normalize_report_defaults(
        input_data.model_dump(by_alias=True, exclude_none=True),
        profile=profile,
        anonymous_session=anonymous_session,
    )
    payload.update(
        {
            **_owner_filter(owner),
            "ownerType": "user" if owner.get("userId") else "anonymous_session",
            "refNo": _generate_ref_no(),
            "consentSnapshot": consent,
            "statusHistory": [_build_history(payload["status"], "created")],
        }
    )
    created = await repository.create_report(payload)
    await _audit(
        owner,
        "report.create",
        "report",
        str(created["_id"]),
        ip=ip,
        user_agent=user_agent,
        metadata={"status": created.get("status")},
    )
    return _serialize_document(created)


async def create_or_update_report_from_conversation(
    conversation_session_id: str,
    owner: dict[str, str | None],
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    bundle = await repository.get_conversation_bundle(conversation_session_id, owner)
    if not bundle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation session not found")
    messages = bundle["messages"]
    facts = bundle["facts"]
    triage = bundle["triage"] or {}
    narrative = "\n".join(
        message.get("content", "") for message in messages if message.get("content")
    )
    structured_fields = {
        "what": [item.get("value") for item in facts if item.get("category") == "incident"],
        "where": [item.get("value") for item in facts if item.get("category") == "location"],
    }
    create_input = CreateReportInput(
        language=bundle["session"].get("language") or "en",
        jurisdiction=bundle["session"].get("jurisdiction") or "NSW",
        originalNarrative=narrative or None,
        incidentType=triage.get("incidentType"),
        severity=triage.get("severity"),
        structuredFields=structured_fields,
    )
    return await create_report(
        owner,
        create_input,
        ip=ip,
        user_agent=user_agent,
        repository=repository,
    )


async def list_reports(
    owner: dict[str, str | None],
    *,
    repository: ReportsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_reports_repository()
    reports = await repository.list_reports(owner)
    return [_serialize_document(item) for item in reports]


async def get_report(
    report_id: str,
    owner: dict[str, str | None],
    *,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    report = await repository.find_report_for_owner(report_id, owner)
    if not report or report.get("deletedAt"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return _serialize_document(report)


async def update_report(
    report_id: str,
    owner: dict[str, str | None],
    input_data: UpdateReportInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    report = await repository.find_report_for_owner(report_id, owner)
    if not report or report.get("deletedAt"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    consent = await _require_cloud_sync_consent(owner)
    profile = await repository.get_profile(owner)
    anonymous_session = await repository.get_anonymous_session(owner.get("sessionId"))
    payload = _normalize_report_defaults(
        input_data.model_dump(by_alias=True, exclude_none=True),
        profile=profile,
        anonymous_session=anonymous_session,
    )
    payload["consentSnapshot"] = consent
    if payload.get("status"):
        payload["statusHistory"] = [
            *(report.get("statusHistory") or []),
            _build_history(payload["status"], "updated"),
        ]
    updated = await repository.update_report(report_id, owner, payload)
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    await _audit(
        owner,
        "report.update",
        "report",
        report_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"changedFields": list(payload.keys())},
    )
    return _serialize_document(updated)


async def delete_report(
    report_id: str,
    owner: dict[str, str | None],
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    report = await repository.append_report_history(
        report_id,
        owner,
        _build_history(REPORT_STATUS_DELETED, "soft_delete"),
        {"status": REPORT_STATUS_DELETED, "deletedAt": datetime.now(UTC)},
    )
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    await _audit(owner, "report.delete", "report", report_id, ip=ip, user_agent=user_agent)
    return _serialize_document(report)


async def mark_report_info_only(
    report_id: str,
    owner: dict[str, str | None],
    input_data: MarkInfoOnlyInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    report = await repository.find_report_for_owner(report_id, owner)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    consent = await get_current_consent(owner)
    updates: dict[str, Any] = {"status": REPORT_STATUS_INFO_ONLY}
    if not consent.get("anonymised_analytics"):
        updates["originalNarrative"] = None
        updates["translatedNarrative"] = None
        updates["structuredFields"] = {}
    marked = await repository.append_report_history(
        report_id,
        owner,
        _build_history(REPORT_STATUS_INFO_ONLY, input_data.reason or "mark_info_only"),
        updates,
    )
    await _audit(owner, "report.mark_info_only", "report", report_id, ip=ip, user_agent=user_agent)
    return _serialize_document(marked)


async def withdraw_report(
    report_id: str,
    owner: dict[str, str | None],
    input_data: WithdrawReportInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    report = await repository.find_report_for_owner(report_id, owner)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if report.get("status") in WITHDRAW_BLOCKED_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Report can no longer be withdrawn")
    withdrawn = await repository.append_report_history(
        report_id,
        owner,
        _build_history(REPORT_STATUS_WITHDRAWN, input_data.reason or "withdrawn"),
        {"status": REPORT_STATUS_WITHDRAWN, "withdrawnAt": datetime.now(UTC)},
    )
    await _audit(owner, "report.withdraw", "report", report_id, ip=ip, user_agent=user_agent)
    return _serialize_document(withdrawn)


async def request_report_delete(
    report_id: str,
    owner: dict[str, str | None],
    input_data: RequestDeleteInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    report = await repository.append_report_history(
        report_id,
        owner,
        _build_history(REPORT_STATUS_DELETED, input_data.reason or "deletion_requested"),
        {"status": REPORT_STATUS_DELETED, "deletionRequestedAt": datetime.now(UTC)},
    )
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    await _audit(owner, "report.request_delete", "report", report_id, ip=ip, user_agent=user_agent)
    return _serialize_document(report)


async def get_report_status(
    report_id: str,
    owner: dict[str, str | None],
    *,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    report = await get_report(report_id, owner, repository=repository)
    return {
        "id": report["_id"],
        "refNo": report.get("refNo"),
        "current": report.get("status"),
        "status": report.get("status"),
        "updatedAt": report.get("updatedAt"),
        "localOnly": report.get("status") == "local_only",
        "deletionRequestedAt": report.get("deletionRequestedAt"),
        "withdrawnAt": report.get("withdrawnAt"),
    }


async def get_report_timeline(
    report_id: str,
    owner: dict[str, str | None],
    *,
    repository: ReportsRepository | None = None,
) -> list[dict[str, Any]]:
    report = await get_report(report_id, owner, repository=repository)
    return [_serialize_value(item) for item in (report.get("statusHistory") or [])]


async def get_report_destinations(
    report_id: str,
    owner: dict[str, str | None],
    *,
    repository: ReportsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_reports_repository()
    report = await repository.find_report_for_owner(report_id, owner)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    destinations = await repository.get_destinations(
        report.get("jurisdiction") or "NSW", report.get("incidentType")
    )
    consent = await get_current_consent(owner)
    evidence = await repository.list_evidence_for_report(report_id, owner)
    previews = []
    for destination in destinations:
        template = await repository.get_template_for_destination(str(destination["_id"]))
        previews.append(
            _build_destination_preview(
                report,
                destination,
                template,
                evidence,
                consent,
                "identified",
            )
        )
    return previews


async def list_report_submissions(
    report_id: str,
    owner: dict[str, str | None],
    *,
    repository: ReportsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_reports_repository()
    submissions = await repository.list_submissions_for_report(report_id, owner)
    return [_serialize_document(item) for item in submissions]


async def create_submission_previews(
    report_id: str,
    owner: dict[str, str | None],
    input_data: SubmissionPreviewInput,
    *,
    repository: ReportsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_reports_repository()
    report = await repository.find_report_for_owner(report_id, owner)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    consent = await get_current_consent(owner)
    evidence = await repository.list_evidence_for_report(report_id, owner)
    previews = []
    for destination_id in input_data.destination_ids:
        destination = await repository.get_destination(destination_id)
        if not destination:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Destination not found")
        template = await repository.get_template_for_destination(destination_id)
        previews.append(
            _build_destination_preview(
                report,
                destination,
                template,
                evidence,
                consent,
                input_data.anonymity_mode,
                input_data.notes,
            )
        )
    return previews


def _ensure_submission_consent(consent: dict[str, bool], flags: list[str]) -> None:
    missing = [flag for flag in flags if not consent.get(flag)]
    if missing:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Required consent is missing: {', '.join(missing)}",
        )


async def _export_manual_artifact(submission: dict[str, Any]) -> list[dict[str, Any]]:
    settings = get_settings()
    export_dir = settings.REPORT_DELIVERY_EXPORT_PATH
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"{submission['_id']}.json"
    export_path.write_text(json.dumps(_serialize_document(submission), indent=2), encoding="utf-8")
    return [{"type": "manual_export_json", "fileName": export_path.name}]


async def create_submission(
    report_id: str,
    owner: dict[str, str | None],
    input_data: CreateSubmissionInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    report = await repository.find_report_for_owner(report_id, owner)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if report.get("status") in {REPORT_STATUS_WITHDRAWN, "closed", REPORT_STATUS_DELETED}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Report cannot be submitted in its current state",
        )
    destination = await repository.get_destination(input_data.destination_id)
    if not destination:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Destination not found")
    consent = await get_current_consent(owner)
    evidence = await repository.list_evidence_for_report(report_id, owner)
    preview = _build_destination_preview(
        report,
        destination,
        await repository.get_template_for_destination(input_data.destination_id),
        evidence,
        consent,
        input_data.anonymity_mode,
        input_data.notes,
    )
    if preview["missingRequiredInfo"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Report is missing required information for submission",
        )
    _ensure_submission_consent(consent, preview["requiredConsentFlags"])
    previous = await repository.find_submission_by_destination(
        report_id, owner, input_data.destination_id
    )
    if previous and previous.get("status") in ACTIVE_SUBMISSION_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Active submission already exists for destination",
        )

    readiness = preview["deliveryReadiness"]
    status_value = readiness["status"]
    submission_payload = {
        **_owner_filter(owner),
        "ownerType": "user" if owner.get("userId") else "anonymous_session",
        "reportId": report_id,
        "destinationId": input_data.destination_id,
        "destinationKey": destination.get("key"),
        "destinationType": destination.get("type"),
        "destinationName": destination.get("name"),
        "channel": destination.get("channel"),
        "jurisdiction": destination.get("jurisdiction"),
        "languages": destination.get("languages") or [report.get("language")],
        "status": status_value,
        "anonymityMode": input_data.anonymity_mode,
        "minimumRequiredInfo": preview["missingRequiredInfo"],
        "missingRequiredInfo": preview["missingRequiredInfo"],
        "requiredConsentFlags": preview["requiredConsentFlags"],
        "expectedNextSteps": readiness["issues"],
        "notes": input_data.notes,
        "payloadSnapshot": preview["payload"],
        "evidenceSnapshot": preview["evidence"],
        "consentSnapshot": consent,
        "previewGeneratedAt": datetime.now(UTC),
        "submittedAt": datetime.now(UTC) if status_value == SUBMISSION_STATUS_SUBMITTED else None,
        "actuallySent": status_value == SUBMISSION_STATUS_SUBMITTED,
    }
    created = await repository.create_submission(submission_payload)
    if status_value == SUBMISSION_STATUS_REQUIRES_MANUAL_ACTION:
        artifacts = await _export_manual_artifact(created)
        created = await repository.update_submission(
            str(created["_id"]),
            report_id,
            owner,
            {"deliveryArtifacts": artifacts, "deliveryMode": destination.get("channel")},
        ) or created

    next_status = REPORT_STATUS_SUBMITTED
    if status_value == SUBMISSION_STATUS_ACKNOWLEDGED:
        next_status = REPORT_STATUS_RECEIVED
    elif status_value in {
        SUBMISSION_STATUS_REQUIRES_MANUAL_ACTION,
        SUBMISSION_STATUS_CONFIG_MISSING,
    }:
        next_status = REPORT_STATUS_PENDING_SUBMISSION
    elif status_value == "failed":
        next_status = REPORT_STATUS_READY_FOR_REVIEW
    await repository.append_report_history(
        report_id,
        owner,
        _build_history(next_status, "submitted_to_destination"),
        {"status": next_status},
    )
    await _audit(
        owner,
        "report.submit_destination",
        "report_submission",
        str(created["_id"]),
        ip=ip,
        user_agent=user_agent,
        metadata={"reportId": report_id, "destinationId": input_data.destination_id},
    )
    return _serialize_document(created)


async def acknowledge_submission(
    report_id: str,
    submission_id: str,
    owner: dict[str, str | None],
    input_data: AcknowledgeSubmissionInput,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    repository: ReportsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_reports_repository()
    existing = await repository.find_submission_for_owner(submission_id, report_id, owner)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report submission not found")
    updated = await repository.update_submission(
        submission_id,
        report_id,
        owner,
        {
            "status": input_data.status,
            "externalReference": input_data.external_reference,
            "acknowledgementMessage": input_data.acknowledgement_message,
            "acknowledgementPayload": input_data.acknowledgement_payload,
            "acknowledgementReceivedAt": datetime.now(UTC),
        },
    )
    if input_data.status == SUBMISSION_STATUS_ACKNOWLEDGED:
        await repository.append_report_history(
            report_id,
            owner,
            _build_history(REPORT_STATUS_RECEIVED, "submission_acknowledged"),
            {"status": REPORT_STATUS_RECEIVED},
        )
    await _audit(
        owner,
        "report.submission_acknowledge",
        "report_submission",
        submission_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"reportId": report_id},
    )
    return _serialize_document(updated)
