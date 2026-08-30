from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import CreateEvidenceUploadUrlInput, TranscribeEvidenceInput, VerifyHashInput
from .service import (
    complete_upload,
    create_upload_url,
    delete_evidence,
    get_evidence,
    get_evidence_audit_chain,
    get_evidence_metadata,
    get_evidence_transcription,
    list_report_evidence,
    transcribe_evidence,
    verify_evidence_hash,
)

router = APIRouter(tags=["evidence"])


def _owner(principal: AuthenticatedSessionOrUser) -> dict[str, str | None]:
    return {"userId": principal.user_id, "sessionId": principal.session_id}


def _request_context(request: Request) -> tuple[str | None, str | None]:
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/evidence/upload-url", status_code=status.HTTP_201_CREATED)
async def create_upload_url_route(
    request: Request,
    input_data: CreateEvidenceUploadUrlInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    payload = await create_upload_url(_owner(principal), input_data, ip=ip, user_agent=user_agent)
    return success("Evidence upload URL created", payload)


@router.post("/evidence/complete-upload")
async def complete_upload_route(
    request: Request,
    principal: AuthenticatedSessionOrUser,
    evidenceId: Annotated[str, Form(...)],
    sha256Hash: Annotated[str, Form(...)],
    file: Annotated[UploadFile | None, File()] = None,
    metadata: Annotated[str | None, Form()] = None,
):
    ip, user_agent = _request_context(request)
    import json

    payload = await complete_upload(
        _owner(principal),
        evidence_id=evidenceId,
        sha256_hash=sha256Hash,
        metadata=json.loads(metadata) if metadata else {},
        file=file,
        ip=ip,
        user_agent=user_agent,
    )
    return success("Evidence upload completed", {"evidence": payload})


@router.get("/reports/{reportId}/evidence")
async def list_report_evidence_route(reportId: str, principal: AuthenticatedSessionOrUser):
    evidence_items = await list_report_evidence(reportId, _owner(principal))
    return success("Evidence retrieved", {"evidence": evidence_items})


@router.get("/evidence/{id}")
async def get_evidence_route(request: Request, id: str, principal: AuthenticatedSessionOrUser):
    ip, user_agent = _request_context(request)
    evidence = await get_evidence(id, _owner(principal), ip=ip, user_agent=user_agent)
    return success("Evidence retrieved", {"evidence": evidence})


@router.delete("/evidence/{id}")
async def delete_evidence_route(
    request: Request, id: str, principal: AuthenticatedSessionOrUser
):
    ip, user_agent = _request_context(request)
    evidence = await delete_evidence(id, _owner(principal), ip=ip, user_agent=user_agent)
    return success("Evidence deleted", {"evidence": evidence})


@router.get("/evidence/{id}/metadata")
async def get_evidence_metadata_route(id: str, principal: AuthenticatedSessionOrUser):
    metadata = await get_evidence_metadata(id, _owner(principal))
    return success("Evidence metadata retrieved", {"metadata": metadata})


@router.get("/evidence/{id}/audit-chain")
async def get_evidence_audit_chain_route(id: str, principal: AuthenticatedSessionOrUser):
    chain = await get_evidence_audit_chain(id, _owner(principal))
    return success("Evidence audit chain retrieved", {"auditChain": chain})


@router.get("/evidence/{id}/transcription")
async def get_evidence_transcription_route(
    request: Request, id: str, principal: AuthenticatedSessionOrUser
):
    ip, user_agent = _request_context(request)
    transcription = await get_evidence_transcription(
        id, _owner(principal), ip=ip, user_agent=user_agent
    )
    return success("Evidence transcription retrieved", {"transcription": transcription})


@router.post("/evidence/{id}/verify-hash")
async def verify_hash_route(
    request: Request,
    id: str,
    input_data: VerifyHashInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    verification = await verify_evidence_hash(
        id, _owner(principal), input_data, ip=ip, user_agent=user_agent
    )
    return success("Evidence hash verified", {"verification": verification})


@router.post("/evidence/{id}/transcribe")
async def transcribe_evidence_route(
    request: Request,
    id: str,
    input_data: TranscribeEvidenceInput,
    principal: AuthenticatedSessionOrUser,
):
    ip, user_agent = _request_context(request)
    transcription = await transcribe_evidence(
        id, _owner(principal), input_data, ip=ip, user_agent=user_agent
    )
    return success("Evidence transcribed", {"transcription": transcription})
