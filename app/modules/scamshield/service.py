import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, UploadFile, status

from app.modules.audit.service import create_audit_log
from app.modules.consent.service import get_current_consent

from .analyzer import build_screenshot_analysis_text
from .model import SCAMSHIELD_ACTIONS
from .repository import ScamShieldRepository, get_scamshield_repository
from .risk_engine import score_content
from .schema import (
    AnalyzeEmailInput,
    AnalyzeScreenshotInput,
    AnalyzeTextInput,
    CheckUrlInput,
    GenerateReportDraftInput,
    RedactScamContentInput,
    SubmitScamReportInput,
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


def _serialize_analysis(document: dict[str, Any]) -> dict[str, Any]:
    payload = {key: _serialize_value(value) for key, value in document.items()}
    if payload.get("_id") is not None:
        payload["_id"] = str(payload["_id"])
    for key in ("userId", "sessionId", "reportId"):
        if payload.get(key) is not None:
            payload[key] = str(payload[key])
    return payload


def _hash_value(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def _audit(
    context: dict[str, Any],
    action: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    owner = context["owner"]
    await create_audit_log(
        actor_type="user" if owner.get("userId") else "anonymous_session",
        actor_id=owner.get("userId"),
        session_id=owner.get("sessionId"),
        action=action,
        resource_type="scamshield_analysis",
        resource_id=resource_id,
        ip=context.get("ip"),
        user_agent=context.get("userAgent"),
        metadata=metadata or {},
    )


async def _assert_ai_consent(owner: dict[str, str | None]) -> dict[str, bool]:
    consent = await get_current_consent(owner)
    if not consent.get("process_with_ai"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "process_with_ai consent is required for ScamShield analysis",
        )
    return consent


async def _assert_share_consent(
    owner: dict[str, str | None], consent_to_share: bool
) -> dict[str, bool]:
    consent = await get_current_consent(owner)
    if consent_to_share and not consent.get("share_with_agencies"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "share_with_agencies consent is required before ScamShield submission",
        )
    return consent


async def _create_analysis(
    context: dict[str, Any],
    analysis_type: str,
    content: str,
    input_payload: dict[str, Any],
    action: str,
    *,
    email_input: dict[str, Any] | None = None,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_scamshield_repository()
    consent = await _assert_ai_consent(context["owner"])
    scored = score_content(
        content,
        analysis_type=analysis_type,
        email_input=email_input,
        url_value=input_payload.get("url"),
    )
    language = (
        input_payload.get("language")
        or (input_payload.get("metadata") or {}).get("language")
        or "en"
    )
    base_analysis = {
        **_owner_filter(context["owner"]),
        "reportId": input_payload.get("reportId"),
        "type": analysis_type,
        "inputHash": _hash_value(input_payload),
        "riskLevel": scored["riskLevel"],
        "riskScore": scored["riskScore"],
        "confidence": scored["confidence"],
        "summary": scored["summary"],
        "indicators": scored["indicators"],
        "redFlags": scored["redFlags"],
        "recommendations": scored["recommendations"],
        "extractedEntities": scored["extractedEntities"],
        "status": "draft",
        "metadata": {
            **(input_payload.get("metadata") or {}),
            "detectionVersion": "scamshield-openai-direct-v1",
            "scoringMode": "openai_direct",
            "confidenceScore": scored["confidenceScore"],
            "matchedSignalCount": len(scored["indicators"]),
            "urlReputation": scored["urlReputation"],
            "senderAnalysis": scored["senderAnalysis"],
            "language": str(language).lower(),
            "storageMode": (
                "server"
                if (consent.get("cloud_sync") or consent.get("share_with_agencies"))
                else "local_only"
            ),
            "informationOnly": True,
            "humanReviewRequired": True,
        },
    }
    if not consent.get("cloud_sync") and not consent.get("share_with_agencies"):
        local = {
            **base_analysis,
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
        }
        await _audit(
            context,
            action,
            None,
            {
                "type": analysis_type,
                "riskLevel": local["riskLevel"],
                "riskScore": local["riskScore"],
                "storageMode": "local_only",
            },
        )
        return _serialize_analysis(local)
    analysis = await repository.create_analysis(base_analysis)
    await _audit(
        context,
        action,
        str(analysis["_id"]),
        {
            "type": analysis_type,
            "riskLevel": analysis.get("riskLevel"),
            "riskScore": analysis.get("riskScore"),
            "storageMode": "server",
        },
    )
    return _serialize_analysis(analysis)


def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "_id": snapshot.get("_id"),
        "type": snapshot.get("type", "text"),
        "inputHash": snapshot.get("inputHash") or _hash_value(snapshot),
        "riskLevel": snapshot.get("riskLevel", "low"),
        "riskScore": snapshot.get("riskScore", 0),
        "confidence": snapshot.get("confidence"),
        "summary": snapshot.get("summary"),
        "indicators": list(snapshot.get("indicators") or []),
        "redFlags": list(snapshot.get("redFlags") or []),
        "recommendations": list(snapshot.get("recommendations") or []),
        "extractedEntities": snapshot.get("extractedEntities"),
        "redactedContent": snapshot.get("redactedContent"),
        "draftReport": snapshot.get("draftReport"),
        "status": snapshot.get("status", "draft"),
        "submittedAt": snapshot.get("submittedAt"),
        "metadata": dict(snapshot.get("metadata") or {}),
        "createdAt": snapshot.get("createdAt") or now,
        "updatedAt": snapshot.get("updatedAt") or now,
        "reportId": snapshot.get("reportId"),
    }


def _redact_text(value: str, replacement: str) -> str:
    redacted = value
    replacement_value = "***" if replacement == "mask" else "[EMAIL]"
    redacted = re.sub(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        replacement_value,
        redacted,
        flags=re.I,
    )
    replacement_value = "***" if replacement == "mask" else "[PHONE]"
    redacted = re.sub(r"\+?\d[\d\s().-]{7,}\d", replacement_value, redacted)
    replacement_value = "***" if replacement == "mask" else "[URL]"
    redacted = re.sub(r"https?://[^\s]+", replacement_value, redacted, flags=re.I)
    replacement_value = "***" if replacement == "mask" else "[AMOUNT]"
    redacted = re.sub(
        r"\b(?:AUD|USD|GBP|EUR)\s?\d[\d,]*(?:\.\d{2})?\b|[$€£]\s?\d[\d,]*(?:\.\d{2})?\b",
        replacement_value,
        redacted,
        flags=re.I,
    )
    replacement_value = "***" if replacement == "mask" else "[TRANSACTION_ID]"
    redacted = re.sub(
        r"\b(?:transaction(?:\s+id)?|txn|txid|receipt|remittance)\s*[:#-]?\s*[A-Z0-9-]{6,}\b",
        replacement_value,
        redacted,
        flags=re.I,
    )
    return redacted


def _get_list(entities: dict[str, Any] | None, key: str) -> list[str]:
    value = (entities or {}).get(key)
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    return []


async def _build_report_draft(
    analysis: dict[str, Any],
    *,
    notes: str | None,
    auto_redact_pii: bool,
    redaction_mode: str,
) -> dict[str, Any]:
    entities = analysis.get("extractedEntities") or {}
    draft_lines = [
        (
            f"ScamShield assessment: {analysis.get('riskLevel')} risk "
            f"({analysis.get('riskScore')}/100), "
            f"{analysis.get('confidence') or 'rule-based'} confidence."
        ),
        f"Summary: {analysis.get('summary')}" if analysis.get("summary") else None,
        (
            f"Detected signals: {', '.join(analysis.get('indicators') or [])}."
            if analysis.get("indicators")
            else "Detected signals: no strong automated scam markers found."
        ),
        (
            f"URLs: {', '.join(_get_list(entities, 'urls')[:3])}."
            if _get_list(entities, "urls")
            else None
        ),
        (
            f"Phone numbers: {', '.join(_get_list(entities, 'phoneNumbers')[:3])}."
            if _get_list(entities, "phoneNumbers")
            else None
        ),
        (
            f"Amounts: {', '.join(_get_list(entities, 'amounts')[:3])}."
            if _get_list(entities, "amounts")
            else None
        ),
        (
            f"Suggested protective actions: {' '.join((analysis.get('recommendations') or [])[:3])}"
            if analysis.get("recommendations")
            else None
        ),
        f"Reporter notes: {notes}" if notes else None,
    ]
    draft_text = "\n\n".join(line for line in draft_lines if line)
    if auto_redact_pii:
        draft_text = _redact_text(draft_text, redaction_mode)
    return {
        "source": "scamshield",
        "summary": analysis.get("summary"),
        "draft": draft_text,
        "riskLevel": analysis.get("riskLevel"),
        "riskScore": analysis.get("riskScore"),
        "confidence": analysis.get("confidence"),
        "indicators": analysis.get("indicators") or [],
        "redFlags": analysis.get("redFlags") or [],
        "recommendations": analysis.get("recommendations") or [],
        "extractedEntities": entities,
        "urlReputation": (analysis.get("metadata") or {}).get("urlReputation"),
        "senderAnalysis": (analysis.get("metadata") or {}).get("senderAnalysis"),
        "scamCategory": "Suspected scam or fraud attempt",
        "platform": "Email" if analysis.get("type") == "email" else "Message text",
        "notes": notes,
        "autoRedactPII": auto_redact_pii,
        "redactionMode": redaction_mode,
        "destinations": {
            "scamwatch": {
                "title": "ACCC Scamwatch",
                "guidanceUrl": "https://www.scamwatch.gov.au/report-a-scam",
            },
            "reportCyber": {
                "title": "ACSC ReportCyber",
                "guidanceUrl": "https://www.cyber.gov.au/report-and-recover/report",
            },
        },
        "informationOnly": True,
        "humanReviewRequired": True,
    }


async def analyze_text(
    context: dict[str, Any],
    input_data: AnalyzeTextInput,
    *,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    return await _create_analysis(
        context,
        "text",
        input_data.text,
        input_data.model_dump(by_alias=True, exclude_none=True),
        SCAMSHIELD_ACTIONS["analyzeText"],
        repository=repository,
    )


async def analyze_email(
    context: dict[str, Any],
    input_data: AnalyzeEmailInput,
    *,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    payload = input_data.model_dump(by_alias=True, exclude_none=True)
    return await _create_analysis(
        context,
        "email",
        f"{payload.get('subject', '')}\n{payload.get('from', '')}\n{payload.get('body', '')}",
        payload,
        SCAMSHIELD_ACTIONS["analyzeEmail"],
        email_input=payload,
        repository=repository,
    )


async def analyze_screenshot(
    context: dict[str, Any],
    input_data: AnalyzeScreenshotInput,
    *,
    files: list[UploadFile] | None = None,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    payload = input_data.model_dump(by_alias=True, exclude_none=True)
    evidence_text = await build_screenshot_analysis_text(payload, files)
    has_document_files = any(
        item.get("extractor") != "openai-vision-ocr" for item in evidence_text["extractedFiles"]
    )
    analysis_type = "evidence" if has_document_files else "screenshot"
    payload["imageText"] = evidence_text["text"]
    payload["imageBase64"] = "[redacted-image-data]" if payload.get("imageBase64") else None
    payload["metadata"] = {
        **(payload.get("metadata") or {}),
        "ocrApplied": evidence_text["ocrApplied"],
        "extractedTextLength": len(evidence_text["text"]),
        "uploadedFiles": [
            {
                "fileName": item.get("fileName"),
                "mimeType": item.get("mimeType"),
                "size": item.get("size"),
                "extractor": item.get("extractor"),
                "extractedTextLength": len(item.get("text") or ""),
            }
            for item in evidence_text["extractedFiles"]
        ],
    }
    return await _create_analysis(
        context,
        analysis_type,
        evidence_text["text"],
        payload,
        SCAMSHIELD_ACTIONS["analyzeScreenshot"],
        repository=repository,
    )


async def check_url(
    context: dict[str, Any],
    input_data: CheckUrlInput,
    *,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    return await _create_analysis(
        context,
        "url",
        input_data.url,
        input_data.model_dump(by_alias=True, exclude_none=True),
        SCAMSHIELD_ACTIONS["checkUrl"],
        repository=repository,
    )


async def get_analysis_by_id(
    context: dict[str, Any],
    analysis_id: str,
    *,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_scamshield_repository()
    analysis = await repository.find_analysis_for_owner(analysis_id, context["owner"])
    if not analysis:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ScamShield analysis not found")
    await _audit(context, SCAMSHIELD_ACTIONS["get"], analysis_id)
    return _serialize_analysis(analysis)


async def redact_scam_content(
    context: dict[str, Any],
    input_data: RedactScamContentInput,
) -> dict[str, Any]:
    await _assert_ai_consent(context["owner"])
    redacted = _redact_text(input_data.text, input_data.replacement)
    await _audit(
        context,
        SCAMSHIELD_ACTIONS["redact"],
        None,
        {"inputHash": _hash_value(input_data.text)},
    )
    return {"redactedText": redacted, "informationOnly": True}


async def generate_report_draft(
    context: dict[str, Any],
    input_data: GenerateReportDraftInput,
    *,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_scamshield_repository()
    if input_data.analysis_id:
        analysis = await repository.find_analysis_for_owner(
            input_data.analysis_id, context["owner"]
        )
        if not analysis:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ScamShield analysis not found")
    else:
        analysis = _normalize_snapshot(input_data.analysis_snapshot or {})
    serialized = _serialize_analysis(analysis)
    serialized["draftReport"] = await _build_report_draft(
        serialized,
        notes=input_data.notes,
        auto_redact_pii=input_data.auto_redact_pii,
        redaction_mode=input_data.redaction_mode,
    )
    if input_data.analysis_id:
        stored = await repository.update_analysis(
            input_data.analysis_id,
            context["owner"],
            {"draftReport": serialized["draftReport"]},
        )
        if stored:
            serialized = _serialize_analysis(stored)
    await _audit(
        context,
        SCAMSHIELD_ACTIONS["generateReportDraft"],
        input_data.analysis_id,
        {"localOnly": not input_data.analysis_id},
    )
    serialized["draftReport"] = serialized.get("draftReport") or await _build_report_draft(
        serialized,
        notes=input_data.notes,
        auto_redact_pii=input_data.auto_redact_pii,
        redaction_mode=input_data.redaction_mode,
    )
    return serialized


async def submit_scam_report(
    context: dict[str, Any],
    input_data: SubmitScamReportInput,
    *,
    repository: ScamShieldRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_scamshield_repository()
    await _assert_share_consent(context["owner"], input_data.consent_to_share)
    if input_data.analysis_id:
        analysis = await repository.find_analysis_for_owner(
            input_data.analysis_id, context["owner"]
        )
        if not analysis:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ScamShield analysis not found")
    else:
        analysis = _normalize_snapshot(input_data.analysis_snapshot or {})
        analysis = await repository.create_analysis(
            {
                **_owner_filter(context["owner"]),
                "reportId": analysis.get("reportId"),
                "type": analysis.get("type", "text"),
                "inputHash": analysis.get("inputHash"),
                "riskLevel": analysis.get("riskLevel", "low"),
                "riskScore": analysis.get("riskScore", 0),
                "confidence": analysis.get("confidence"),
                "summary": analysis.get("summary"),
                "indicators": analysis.get("indicators") or [],
                "redFlags": analysis.get("redFlags") or [],
                "recommendations": analysis.get("recommendations") or [],
                "extractedEntities": analysis.get("extractedEntities"),
                "redactedContent": analysis.get("redactedContent"),
                "draftReport": analysis.get("draftReport"),
                "status": "draft",
                "metadata": {**(analysis.get("metadata") or {}), "materializedFromLocalOnly": True},
            }
        )
    serialized = _serialize_analysis(analysis)
    if not serialized.get("draftReport"):
        serialized["draftReport"] = await _build_report_draft(
            serialized,
            notes=None,
            auto_redact_pii=False,
            redaction_mode="labels",
        )
    metadata = {
        **(serialized.get("metadata") or {}),
        "submissionDestination": input_data.destination,
        "consentToShare": input_data.consent_to_share,
    }
    if input_data.consent_to_share:
        linked_report = await repository.create_report(
            {
                **_owner_filter(context["owner"]),
                "ownerType": "user" if context["owner"].get("userId") else "anonymous_session",
                "refNo": f"SSS-{datetime.now(UTC).strftime('%Y%m%d')}",
                "context": "scamshield",
                "language": metadata.get("language", "en"),
                "jurisdiction": "AU",
                "originalNarrative": (
                    serialized["draftReport"].get("draft") or serialized.get("summary")
                ),
                "incidentType": "cyber_scam",
                "severity": serialized.get("riskLevel"),
                "structuredFields": {
                    "what": serialized.get("summary"),
                },
                "consentSnapshot": await get_current_consent(context["owner"]),
                "status": "pending_submission",
                "statusHistory": [
                    {
                        "status": "pending_submission",
                        "reason": "scamshield_delivery",
                        "changedAt": datetime.now(UTC),
                    }
                ],
            }
        )
        metadata.update(
            {
                "linkedReportId": str(linked_report["_id"]),
                "deliveryStatus": "requires_manual_action",
                "deliveryMode": "manual_export_json",
                "deliveryConfigurationStatus": "requires_manual_action",
                "deliveryConfigurationIssues": [],
                "deliveryActuallySent": False,
                "deliveryMessage": "Manual review queue submission created",
                "deliveryArtifacts": [],
            }
        )
        serialized["reportId"] = str(linked_report["_id"])
    updated = await repository.update_analysis(
        serialized["_id"],
        context["owner"],
        {
            "status": "submitted",
            "submittedAt": datetime.now(UTC),
            "metadata": metadata,
            "draftReport": serialized["draftReport"],
            "reportId": serialized.get("reportId"),
        },
    )
    await _audit(
        context,
        SCAMSHIELD_ACTIONS["submit"],
        serialized["_id"],
        {
            "destination": input_data.destination,
            "consentToShare": input_data.consent_to_share,
            "materializedFromLocalOnly": not input_data.analysis_id,
        },
    )
    return _serialize_analysis(updated or analysis)
