from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.responses import success
from app.core.security import Principal, require_content_admin
from app.services.extraction import extract_pdf

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("")
async def extract_document(
    file: Annotated[UploadFile, File(...)],
    _principal: Annotated[Principal, Depends(require_content_admin)],
):
    data = await file.read()
    extracted = extract_pdf(data, file.filename or "document.pdf")
    return success("PDF extraction completed", extracted.model_dump(mode="json"))

