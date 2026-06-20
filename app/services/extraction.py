import hashlib
import io
import re
import shutil
from collections.abc import Iterable

import fitz
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.extraction import (
    BoundingBox,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
    TextBlock,
    TextSpan,
)

HEADING_RE = re.compile(
    r"^(?:(?:part|division|subdivision|schedule|chapter)\s+[0-9A-Za-z.-]+|"
    r"[0-9]{1,4}[A-Za-z]?\s+[A-Z][^\n]{2,160})",
    re.IGNORECASE,
)


def _bbox(value: Iterable[float]) -> BoundingBox:
    x0, y0, x1, y1 = value
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _table_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [[(cell or "").replace("\n", " ").strip() for cell in row] for row in rows]
    normalized = [row + [""] * (width - len(row)) for row in normalized]
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n".join(lines)


def _ocr_page(page: fitz.Page) -> tuple[str, float | None, list[str]]:
    settings = get_settings()
    if not settings.RAG_ENABLE_OCR:
        return "", None, ["Image-only page detected; OCR is disabled."]
    tessdata_path = settings.TESSDATA_PATH
    if tessdata_path.exists() and (tessdata_path / f"{settings.OCR_LANGUAGE}.traineddata").exists():
        try:
            text_page = page.get_textpage_ocr(
                language=settings.OCR_LANGUAGE,
                dpi=300,
                full=True,
                tessdata=str(tessdata_path.resolve()),
            )
            text = page.get_text("text", textpage=text_page).strip()
            alphanumeric = sum(character.isalnum() for character in text)
            confidence = min(0.99, alphanumeric / max(1, len(text))) if text else 0.0
            warnings = ["OCR confidence is a text-quality estimate; legal review is required."]
            if confidence < settings.OCR_MIN_CONFIDENCE:
                warnings.append(
                    f"OCR quality estimate {confidence:.2f} is below the review threshold."
                )
            return text, confidence, warnings
        except RuntimeError as exc:
            integrated_warning = f"PyMuPDF integrated OCR failed: {exc}"
    else:
        integrated_warning = "PyMuPDF tessdata is unavailable."
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", None, [integrated_warning, "OCR dependencies are not installed. Install .[ocr]."]
    executable = (
        str(settings.TESSERACT_CMD)
        if settings.TESSERACT_CMD and settings.TESSERACT_CMD.exists()
        else shutil.which("tesseract")
    )
    if not executable:
        return "", None, [
            integrated_warning,
            "Tesseract executable is not installed or TESSERACT_CMD is invalid.",
        ]
    pytesseract.pytesseract.tesseract_cmd = executable

    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    data = pytesseract.image_to_data(
        image,
        lang=settings.OCR_LANGUAGE,
        output_type=pytesseract.Output.DICT,
    )
    words: list[str] = []
    confidences: list[float] = []
    for text, confidence in zip(data["text"], data["conf"], strict=False):
        if text.strip():
            words.append(text.strip())
        try:
            value = float(confidence)
            if value >= 0:
                confidences.append(value / 100)
        except (TypeError, ValueError):
            pass
    average = sum(confidences) / len(confidences) if confidences else None
    warnings = []
    if average is not None and average < settings.OCR_MIN_CONFIDENCE:
        warnings.append(f"OCR confidence {average:.2f} is below the review threshold.")
    return " ".join(words), average, warnings


def ocr_health() -> dict[str, object]:
    settings = get_settings()
    configured_path = str(settings.TESSERACT_CMD) if settings.TESSERACT_CMD else None
    executable = (
        configured_path
        if settings.TESSERACT_CMD and settings.TESSERACT_CMD.exists()
        else shutil.which("tesseract")
    )
    tessdata_ready = (
        settings.TESSDATA_PATH.exists()
        and (settings.TESSDATA_PATH / f"{settings.OCR_LANGUAGE}.traineddata").exists()
    )
    ready = tessdata_ready or bool(executable)
    return {
        "enabled": settings.RAG_ENABLE_OCR,
        "ready": ready,
        "provider": "pymupdf_tesseract" if tessdata_ready else "pytesseract",
        "executable": executable,
        "tessdataPath": str(settings.TESSDATA_PATH),
        "language": settings.OCR_LANGUAGE,
        "reviewRequired": settings.OCR_REVIEW_REQUIRED,
        "message": (
            "OCR is ready"
            if ready
            else "Install tessdata/Tesseract or configure TESSDATA_PATH/TESSERACT_CMD"
        ),
    }


def extract_pdf(data: bytes, file_name: str) -> ExtractedDocument:
    settings = get_settings()
    if not data or len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "PDF exceeds upload limit")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Uploaded file is not a PDF")

    pages: list[ExtractedPage] = []
    blocks: list[TextBlock] = []
    tables: list[ExtractedTable] = []
    raw_pages: list[str] = []
    markdown_pages: list[str] = []
    warnings: list[str] = []
    used_ocr = False

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PDF could not be opened",
        ) from exc

    if document.needs_pass:
        document.close()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Encrypted PDFs are not supported",
        )

    try:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            page_dict = page.get_text("dict", sort=True)
            page_spans: list[TextSpan] = []
            page_blocks: list[TextBlock] = []
            text_parts: list[str] = []

            for raw_block in page_dict.get("blocks", []):
                if raw_block.get("type") != 0:
                    continue
                block_spans: list[TextSpan] = []
                line_texts: list[str] = []
                for line in raw_block.get("lines", []):
                    span_texts: list[str] = []
                    for span in line.get("spans", []):
                        text = str(span.get("text", ""))
                        if not text:
                            continue
                        font_name = str(span.get("font", ""))
                        item = TextSpan(
                            text=text,
                            pageNumber=page_number,
                            bbox=_bbox(span.get("bbox", (0, 0, 0, 0))),
                            fontSize=float(span.get("size", 0)),
                            fontName=font_name,
                            isBold="bold" in font_name.lower() or bool(span.get("flags", 0) & 16),
                        )
                        page_spans.append(item)
                        block_spans.append(item)
                        span_texts.append(text)
                    if span_texts:
                        line_texts.append("".join(span_texts).strip())

                block_text = "\n".join(filter(None, line_texts)).strip()
                if not block_text:
                    continue
                text_parts.append(block_text)
                max_size = max((span.fontSize for span in block_spans), default=0)
                is_bold = any(span.isBold for span in block_spans)
                is_heading = bool(HEADING_RE.match(block_text)) or (
                    is_bold and len(block_text) < 180
                )
                block = TextBlock(
                    text=block_text,
                    pageStart=page_number,
                    pageEnd=page_number,
                    bbox=_bbox(raw_block.get("bbox", (0, 0, 0, 0))),
                    fontSize=max_size,
                    isBold=is_bold,
                    blockType="heading" if is_heading else "text",
                )
                blocks.append(block)
                page_blocks.append(block)

            page_text = "\n".join(text_parts).strip()
            ocr_used = False
            ocr_confidence = None
            page_warnings: list[str] = []
            if len(re.sub(r"\s+", "", page_text)) < 10:
                ocr_text, ocr_confidence, page_warnings = _ocr_page(page)
                if ocr_text:
                    page_text = ocr_text
                    ocr_used = used_ocr = True
                    ocr_block = TextBlock(
                        text=ocr_text,
                        pageStart=page_number,
                        pageEnd=page_number,
                        bbox=_bbox(page.rect),
                        fontSize=0,
                        isBold=False,
                        blockType="text",
                    )
                    blocks.append(ocr_block)
                    page_blocks.append(ocr_block)

            page_tables: list[ExtractedTable] = []
            try:
                finder = page.find_tables()
                for found in finder.tables:
                    rows = [
                        ["" if cell is None else str(cell) for cell in row]
                        for row in found.extract()
                    ]
                    table = ExtractedTable(
                        pageNumber=page_number,
                        bbox=_bbox(found.bbox),
                        rows=rows,
                        markdown=_table_markdown(rows),
                    )
                    tables.append(table)
                    page_tables.append(table)
            except Exception as exc:
                page_warnings.append(f"Table detection failed on page {page_number}: {exc}")

            page_markdown = page_text
            if page_tables:
                rendered = "\n\n".join(
                    f"[Table {index} - page {page_number}]\n{table.markdown}"
                    for index, table in enumerate(page_tables, start=1)
                )
                page_markdown = f"{page_text}\n\n{rendered}".strip()

            raw_pages.append(f"{page_text}\n-- {page_number} of {len(document)} --")
            markdown_pages.append(f"<!-- page:{page_number} -->\n{page_markdown}")
            warnings.extend(page_warnings)
            pages.append(
                ExtractedPage(
                    number=page_number,
                    text=page_text,
                    spans=page_spans,
                    ocrUsed=ocr_used,
                    ocrConfidence=ocr_confidence,
                    warnings=page_warnings,
                )
            )
    finally:
        document.close()

    return ExtractedDocument(
        fileName=file_name,
        sha256=hashlib.sha256(data).hexdigest(),
        pageCount=len(pages),
        extractionMethod="pymupdf_ocr" if used_ocr else "pymupdf",
        rawText="\n".join(raw_pages).strip(),
        markdown="\n\n".join(markdown_pages).strip(),
        pages=pages,
        blocks=blocks,
        tables=tables,
        warnings=warnings,
    )
