from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.modules.audit.service import create_audit_log

from .repository import PrivacyRepository, get_privacy_repository
from .schema import CreatePrivacyRequestInput, DeleteRequestInput


def owner_filter(owner: dict[str, str | None]) -> dict[str, str]:
    if owner.get("userId"):
        return {"userId": owner["userId"]}
    if owner.get("sessionId"):
        return {"sessionId": owner["sessionId"]}
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User or anonymous session is required")


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
        resource_type="system",
        resource_id=resource_id,
        ip=context.get("ip"),
        user_agent=context.get("userAgent"),
        metadata=metadata,
    )


def _serialize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    result = dict(document)
    if result.get("_id") is not None:
        result["_id"] = str(result["_id"])
    for key in (
        "userId",
        "sessionId",
        "reviewedBy",
        "actorId",
        "resourceId",
        "conversationSessionId",
    ):
        if result.get(key) is not None:
            result[key] = str(result[key])
    return result


def strip_evidence_storage_secrets(evidence: dict[str, Any]) -> dict[str, Any]:
    safe_evidence = dict(evidence)
    for key in (
        "encryptionKeyRef",
        "localEncryptedPath",
        "storageKey",
        "s3",
        "encryption",
    ):
        safe_evidence.pop(key, None)
    safe_evidence["fileContentIncluded"] = False
    safe_evidence["storageSecretsIncluded"] = False
    return safe_evidence


async def create_privacy_request(
    context: dict[str, Any],
    input_data: CreatePrivacyRequestInput,
    *,
    repository: PrivacyRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_privacy_repository()
    if not input_data.confirmation:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Privacy request confirmation is required",
        )
    request = await repository.create_privacy_request(
        {
            **owner_filter(context["owner"]),
            "requestType": input_data.request_type,
            "notes": input_data.notes,
            "status": "pending",
        }
    )
    await _audit(
        context,
        "privacy.request.create",
        str(request["_id"]),
        {"requestType": input_data.request_type},
    )
    return _serialize_document(request)


async def list_own_privacy_requests(
    context: dict[str, Any],
    *,
    repository: PrivacyRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_privacy_repository()
    requests = await repository.list_privacy_requests(owner_filter(context["owner"]))
    await _audit(context, "privacy.request.list", metadata={"count": len(requests)})
    return [_serialize_document(item) for item in requests]


async def get_own_privacy_request(
    context: dict[str, Any],
    request_id: str,
    *,
    repository: PrivacyRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_privacy_repository()
    request = await repository.get_privacy_request(owner_filter(context["owner"]), request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Privacy request not found")
    await _audit(context, "privacy.request.get", request_id)
    return _serialize_document(request)


async def create_deletion_request(
    context: dict[str, Any],
    input_data: DeleteRequestInput,
    *,
    repository: PrivacyRepository | None = None,
) -> dict[str, Any]:
    return await create_privacy_request(
        context,
        CreatePrivacyRequestInput(
            requestType="data_deletion",
            notes=input_data.notes,
            confirmation=input_data.confirmation,
        ),
        repository=repository,
    )


async def get_privacy_export(
    context: dict[str, Any],
    *,
    repository: PrivacyRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_privacy_repository()
    owner = owner_filter(context["owner"])
    conversation_sessions = await repository.get_owner_documents(
        "conversation_sessions",
        owner,
        sort=[("createdAt", -1)],
    )
    conversation_session_ids = [
        ObjectId(session["_id"])
        for session in conversation_sessions
        if isinstance(session.get("_id"), ObjectId)
    ]
    user = await repository.get_user_for_export(owner.get("userId"))
    anonymous_session = await repository.get_anonymous_session_for_export(owner.get("sessionId"))
    profile = await repository.get_profile_for_export(owner)
    consent_history = await repository.get_consent_history_for_export(owner)
    reports = await repository.get_owner_documents("reports", owner, sort=[("createdAt", -1)])
    report_submissions = await repository.get_owner_documents(
        "report_submissions", owner, sort=[("createdAt", -1)]
    )
    evidence = await repository.get_owner_documents("evidence", owner, sort=[("createdAt", -1)])
    ai_interactions = await repository.get_owner_documents(
        "ai_interactions", owner, sort=[("createdAt", -1)]
    )
    scamshield_analyses = await repository.get_owner_documents(
        "scamshield_analyses", owner, sort=[("createdAt", -1)]
    )
    warm_referrals = await repository.get_owner_documents(
        "warm_referrals", owner, sort=[("createdAt", -1)]
    )
    advocate_requests = await repository.get_owner_documents(
        "advocate_requests", owner, sort=[("createdAt", -1)]
    )
    help_support_requests = await repository.get_owner_documents(
        "help_support_requests", owner, sort=[("createdAt", -1)]
    )
    safety_plans = await repository.get_owner_documents(
        "safety_plans", owner, sort=[("createdAt", -1)]
    )
    privacy_requests = await repository.list_privacy_requests(owner)
    audit_logs = await repository.get_audit_logs_for_owner(owner)
    conversation_messages = await repository.get_conversation_children(
        conversation_session_ids, "conversation_messages"
    )
    conversation_facts = await repository.get_conversation_children(
        conversation_session_ids, "conversation_facts"
    )
    conversation_triage = await repository.get_conversation_children(
        conversation_session_ids, "conversation_triage"
    )

    export_payload = {
        "exportVersion": 1,
        "exportedAt": context["exportedAt"],
        "owner": {
            "type": "user" if owner.get("userId") else "anonymous_session",
            "userId": owner.get("userId"),
            "sessionId": owner.get("sessionId"),
        },
        "user": _serialize_document(user),
        "anonymousSession": _serialize_document(anonymous_session),
        "profile": _serialize_document(profile),
        "consentHistory": [_serialize_document(item) for item in consent_history],
        "reports": [_serialize_document(item) for item in reports],
        "reportSubmissions": [_serialize_document(item) for item in report_submissions],
        "evidence": [
            strip_evidence_storage_secrets(_serialize_document(item)) for item in evidence
        ],
        "auditRecords": [_serialize_document(item) for item in audit_logs],
        "aiInteractions": [_serialize_document(item) for item in ai_interactions],
        "conversationFlow": {
            "sessions": [_serialize_document(item) for item in conversation_sessions],
            "messages": [_serialize_document(item) for item in conversation_messages],
            "facts": [_serialize_document(item) for item in conversation_facts],
            "triage": [_serialize_document(item) for item in conversation_triage],
        },
        "scamShieldAnalyses": [_serialize_document(item) for item in scamshield_analyses],
        "support": {
            "warmReferrals": [_serialize_document(item) for item in warm_referrals],
            "advocateRequests": [_serialize_document(item) for item in advocate_requests],
            "helpSupportRequests": [_serialize_document(item) for item in help_support_requests],
            "safetyPlans": [_serialize_document(item) for item in safety_plans],
        },
        "privacyRequests": [_serialize_document(item) for item in privacy_requests],
        "limitations": {
            "evidenceFileBinariesIncluded": False,
            "evidenceStorageSecretsIncluded": False,
            "adminOnlyDataIncluded": False,
        },
    }
    await _audit(
        context,
        "privacy.export.download",
        metadata={
            "reports": len(reports),
            "evidence": len(evidence),
            "consentVersions": len(consent_history),
            "privacyRequests": len(privacy_requests),
        },
    )
    return export_payload
