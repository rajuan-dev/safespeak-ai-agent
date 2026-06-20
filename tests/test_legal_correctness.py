from app.models.extraction import (
    BoundingBox,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
    TextBlock,
)
from app.services.chunking import chunk_extracted_document
from app.services.citation_verifier import verify_grounded_answer
from app.services.reranking import deterministic_rerank


def block(text: str, page: int, *, heading: bool = False) -> TextBlock:
    return TextBlock(
        text=text,
        pageStart=page,
        pageEnd=page,
        bbox=BoundingBox(x0=0, y0=0, x1=500, y1=30),
        fontSize=14 if heading else 10,
        isBold=heading,
        blockType="heading" if heading else "text",
    )


def test_status_dates_tables_and_cross_references_are_attached():
    extracted = ExtractedDocument(
        fileName="act.pdf",
        sha256="b" * 64,
        pageCount=2,
        extractionMethod="pymupdf",
        rawText="Example Act 2026\nAs at 21 June 2026",
        markdown="",
        pages=[],
        blocks=[
            block("3 Reporting duty", 1, heading=True),
            block("(1) Records must be retained for 7 years.", 1),
            block("4 Former notice provision", 2, heading=True),
            block("Repealed by Example Amendment Act 2026.", 2),
            block("5 Related provision", 2, heading=True),
            block("See section 3 of the Example Act 2026.", 2),
        ],
        tables=[
            ExtractedTable(
                pageNumber=1,
                bbox=None,
                rows=[["Item", "Period"], ["Record", "7 years"]],
                markdown="| Item | Period |\n| --- | --- |\n| Record | 7 years |",
            )
        ],
    )
    chunks = chunk_extracted_document(
        extracted,
        {
            "title": "Example Act 2026",
            "legislationName": "Example Act 2026",
            "sourceType": "Act",
        },
    )

    section_three = next(item for item in chunks if item["sectionRef"] == "3(1)")
    section_four = next(item for item in chunks if item["sectionRef"] == "4")
    section_five = next(item for item in chunks if item["sectionRef"] == "5")

    assert section_three["metadata"]["versionDate"] == "2026-06-21"
    assert section_three["metadata"]["tables"][0]["rows"][1] == ["Record", "7 years"]
    assert section_four["metadata"]["amendmentStatus"] == "repealed"
    assert section_four["metadata"]["amendingInstrument"] == "Example Amendment Act 2026"
    assert section_five["metadata"]["crossReferences"][0]["sectionRef"] == "3"


def test_exact_reference_reranking_places_requested_provision_first():
    results = [
        {"chunkId": "general", "sectionRef": "8", "text": "General reporting rules."},
        {"chunkId": "exact", "sectionRef": "12(1)(a)", "text": "The exact reporting duty."},
    ]
    ranked = deterministic_rerank("What does section 12(1)(a) require?", results)
    assert ranked[0]["chunkId"] == "exact"


def test_sentence_level_citation_gate_accepts_supported_claim():
    sources = [
        {
            "title": "Example Act 2026",
            "sectionRef": "3(1)",
            "pageNumber": 1,
            "versionDate": "2026-06-21",
            "citationUrl": "https://example.gov.au/act",
            "text": "Records must be retained for 7 years.",
            "metadata": {"pageStart": 1},
        }
    ]
    result = verify_grounded_answer(
        "Section 3(1) requires records to be retained for 7 years. [SOURCE 1]",
        sources,
    )
    assert result.supported


def test_sentence_level_citation_gate_rejects_unsupported_number():
    sources = [
        {
            "title": "Example Act 2026",
            "sectionRef": "3(1)",
            "pageNumber": 1,
            "versionDate": "2026-06-21",
            "citationUrl": "https://example.gov.au/act",
            "text": "Records must be retained for 7 years.",
            "metadata": {"pageStart": 1},
        }
    ]
    result = verify_grounded_answer(
        "Section 3(1) requires records to be retained for 10 years. [SOURCE 1]",
        sources,
    )
    assert not result.supported
    assert "sentence_1:unsupported_number" in result.errors


def test_contents_and_endnotes_are_not_chunked_as_operational_sections():
    extracted = ExtractedDocument(
        fileName="act.pdf",
        sha256="c" * 64,
        pageCount=3,
        extractionMethod="pymupdf",
        rawText="",
        markdown="",
        pages=[
            ExtractedPage(
                number=1,
                text=(
                    "Contents\n"
                    "1 Short title................1\n"
                    "2 Definitions................2\n"
                    "99 Contents-only provision................9"
                ),
                spans=[],
            ),
            ExtractedPage(number=2, text="Part 1 Preliminary\n3 Real duty", spans=[]),
            ExtractedPage(
                number=3,
                text="Endnotes\n88 Amendment history entry",
                spans=[],
            ),
        ],
        blocks=[
            block("99 Contents-only provision", 1, heading=True),
            block("3 Real duty", 2, heading=True),
            block("(1) A person must comply.", 2),
            block("88 Amendment history entry", 3, heading=True),
        ],
        tables=[],
    )
    chunks = chunk_extracted_document(
        extracted,
        {"title": "Example Act 2026", "sourceType": "Act"},
    )
    refs = {chunk.get("sectionRef") for chunk in chunks}
    assert "3" in refs
    assert "99" not in refs
    assert "88" not in refs


def test_table_of_provisions_is_not_chunked_as_operational_text():
    extracted = ExtractedDocument(
        fileName="victorian-act.pdf",
        sha256="d" * 64,
        pageCount=2,
        extractionMethod="pymupdf",
        rawText="",
        markdown="",
        pages=[
            ExtractedPage(
                number=1,
                text=(
                    "TABLE OF PROVISIONS\n"
                    "7 Human rights—what they are................4\n"
                    "8 Recognition and equality before the law................5\n"
                    "38 Conduct of public authorities................22"
                ),
                spans=[],
            ),
            ExtractedPage(
                number=2,
                text="Part 2 Human rights\n7 Human rights—what they are",
                spans=[],
            ),
        ],
        blocks=[
            block("7 Human rights—what they are", 1, heading=True),
            block("8 Recognition and equality before the law", 1, heading=True),
            block("38 Conduct of public authorities", 1, heading=True),
            block("7 Human rights—what they are", 2, heading=True),
            block("(1) This Part sets out human rights.", 2),
        ],
        tables=[],
    )
    chunks = chunk_extracted_document(
        extracted,
        {
            "title": "Charter of Human Rights and Responsibilities Act 2006",
            "sourceType": "Act",
        },
    )
    refs = [chunk.get("sectionRef") for chunk in chunks]
    assert refs.count("7") == 1
    assert "8" not in refs
    assert "38" not in refs
