import base64
from typing import Any

from fastapi import HTTPException, UploadFile, status

SUPPORTED_EVIDENCE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def build_screenshot_analysis_text(
    input_data: dict[str, Any],
    files: list[UploadFile] | None = None,
) -> dict[str, Any]:
    files = files or []
    extracted_files: list[dict[str, Any]] = []
    text_parts: list[str] = []
    if input_data.get("imageText"):
        text_parts.append(str(input_data["imageText"]))
    if input_data.get("imageBase64"):
        try:
            decoded = base64.b64decode(str(input_data["imageBase64"]))
            if decoded:
                text_parts.append("[image supplied]")
        except Exception as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid imageBase64 payload") from exc
    for file in files:
        if file.content_type not in SUPPORTED_EVIDENCE_MIME_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Unsupported ScamShield evidence file type. Upload an image, "
                "screenshot, PDF, or Word document.",
            )
        content = await file.read()
        text = content.decode("utf-8", errors="ignore")[:20000] or f"[{file.filename} uploaded]"
        extractor = (
            "openai-vision-ocr"
            if str(file.content_type).startswith("image/")
            else "document"
        )
        extracted_files.append(
            {
                "fileName": file.filename,
                "mimeType": file.content_type,
                "size": len(content),
                "text": text,
                "extractor": extractor,
            }
        )
        text_parts.append(text)
    if not text_parts:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "imageText or imageBase64 is required")
    merged = "\n".join(part for part in text_parts if part).strip()
    return {
        "text": merged,
        "ocrApplied": bool(files or input_data.get("imageBase64")),
        "extractedFiles": extracted_files,
    }
