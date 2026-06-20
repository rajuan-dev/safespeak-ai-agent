import fitz
import pytest

from app.services.extraction import extract_pdf, ocr_health


def test_pdf_extraction_preserves_page_and_font_metadata():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Part 1 Preliminary", fontsize=16, fontname="hebo")
    page.insert_text((72, 100), "1 Short title", fontsize=12)
    data = document.tobytes()
    document.close()

    extracted = extract_pdf(data, "example-act.pdf")

    assert extracted.pageCount == 1
    assert extracted.pages[0].number == 1
    assert any(span.fontSize == 16 for span in extracted.pages[0].spans)
    assert "Part 1 Preliminary" in extracted.rawText
    assert extracted.sha256


@pytest.mark.skipif(not ocr_health()["ready"], reason="OCR tessdata is not installed")
def test_image_only_pdf_uses_integrated_ocr():
    source = fitz.open()
    source_page = source.new_page(width=700, height=150)
    source_page.insert_text((40, 95), "SAFE LEGAL RECORD", fontsize=55, fontname="hebo")
    image_bytes = source_page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
    source.close()

    document = fitz.open()
    page = document.new_page(width=700, height=150)
    page.insert_image(page.rect, stream=image_bytes)
    data = document.tobytes()
    document.close()

    extracted = extract_pdf(data, "scan.pdf")

    assert extracted.extractionMethod == "pymupdf_ocr"
    assert extracted.pages[0].ocrUsed
    assert "SAFE LEGAL RECORD" in extracted.pages[0].text.upper()
