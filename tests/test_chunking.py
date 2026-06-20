from app.models.extraction import BoundingBox, ExtractedDocument, TextBlock
from app.services.chunking import chunk_extracted_document


def block(text: str, page: int, *, heading: bool = False) -> TextBlock:
    return TextBlock(
        text=text,
        pageStart=page,
        pageEnd=page,
        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20),
        fontSize=14 if heading else 10,
        isBold=heading,
        blockType="heading" if heading else "text",
    )


def test_legal_hierarchy_and_pages_are_preserved():
    extracted = ExtractedDocument(
        fileName="act.pdf",
        sha256="a" * 64,
        pageCount=2,
        extractionMethod="pymupdf",
        rawText="",
        markdown="",
        pages=[],
        tables=[],
        blocks=[
            block("Part 2 Duties", 1, heading=True),
            block("Division 1 General", 1, heading=True),
            block("12 Duty to report", 1, heading=True),
            block("(1) A person must report the matter.", 1),
            block("(a) the first condition applies;", 1),
            block("(i) subject to the stated exception.", 2),
        ],
    )
    chunks = chunk_extracted_document(
        extracted,
        {"title": "Example Act 2026", "sourceType": "Act"},
    )

    paragraph = next(item for item in chunks if item["sectionRef"] == "12(1)(a)")
    subparagraph = next(item for item in chunks if item["sectionRef"] == "12(1)(a)(i)")

    assert paragraph["metadata"]["pageStart"] == 1
    assert subparagraph["metadata"]["pageStart"] == 2
    assert subparagraph["metadata"]["hierarchyPath"][-1] == {
        "type": "subparagraph",
        "value": "i",
    }


def test_government_report_chunks_are_page_bounded_and_size_limited():
    long_report_text = "This report sentence contains statistical context. " * 180
    extracted = ExtractedDocument(
        fileName="report.pdf",
        sha256="b" * 64,
        pageCount=2,
        extractionMethod="pymupdf",
        rawText="",
        markdown="",
        pages=[],
        tables=[],
        blocks=[
            block("4 in 5 defendants were male.", 1, heading=True),
            block(long_report_text, 1),
            block("6 in 7 matters included an allegation.", 2, heading=True),
            block(long_report_text, 2),
        ],
    )

    chunks = chunk_extracted_document(
        extracted,
        {"title": "Government report", "sourceType": "Report"},
    )

    assert all(chunk["sectionRef"] is None for chunk in chunks)
    assert all(
        chunk["metadata"]["pageStart"] == chunk["metadata"]["pageEnd"]
        for chunk in chunks
    )
    assert all(len(chunk["chunkText"]) <= 2400 for chunk in chunks)
    assert {chunk["pageNumber"] for chunk in chunks} == {1, 2}
