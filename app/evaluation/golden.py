import argparse
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.models.extraction import ExtractedDocument
from app.services.chunking import chunk_extracted_document
from app.services.extraction import extract_pdf
from app.services.reranking import deterministic_rerank


class ExpectedSection(BaseModel):
    sectionRef: str
    page: int | None = None
    status: Literal["in_force", "amended", "repealed"] | None = None


class GoldenQuestion(BaseModel):
    question: str
    expectedSectionRef: str
    expectedRank: int = Field(default=1, ge=1, le=10)


class GoldenExpectations(BaseModel):
    minimumPages: int = Field(default=1, ge=1)
    minimumSections: int = Field(default=1, ge=1)
    requiredText: list[str] = Field(default_factory=list)
    expectedSections: list[ExpectedSection] = Field(default_factory=list)
    tableCellValues: list[str] = Field(default_factory=list)
    scheduleRequired: bool = False
    versionDate: str | None = None


class GoldenFixture(BaseModel):
    id: str
    fixtureType: Literal["reviewed_real", "candidate_real", "synthetic"]
    pdfPath: str
    title: str
    jurisdiction: str
    sourceUrl: str | None = None
    sha256: str | None = None
    expectations: GoldenExpectations
    questions: list[GoldenQuestion] = Field(default_factory=list)


class GoldenManifest(BaseModel):
    fixtures: list[GoldenFixture]


class FixtureReport(BaseModel):
    id: str
    passed: bool
    errors: list[str]
    pageCount: int
    sectionCount: int
    questionCount: int


class GoldenReport(BaseModel):
    passed: bool
    productionReady: bool
    realFixtureCount: int
    jurisdictionCount: int
    totalQuestions: int
    fixtureReports: list[FixtureReport]
    productionBlockers: list[str]


def load_manifest(path: Path) -> GoldenManifest:
    return GoldenManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _source(fixture: GoldenFixture) -> dict[str, object]:
    return {
        "title": fixture.title,
        "legislationName": fixture.title,
        "sourceType": "Act",
        "jurisdiction": fixture.jurisdiction,
        "officialUrl": fixture.sourceUrl,
        "metadata": {},
    }


def _evaluate_fixture(
    fixture: GoldenFixture,
    extracted: ExtractedDocument,
) -> FixtureReport:
    errors: list[str] = []
    chunks = chunk_extracted_document(extracted, _source(fixture))
    sections = {
        str(chunk.get("sectionRef")): chunk
        for chunk in chunks
        if chunk.get("sectionRef")
    }
    if extracted.pageCount < fixture.expectations.minimumPages:
        errors.append("page_count_below_expected")
    if len(sections) < fixture.expectations.minimumSections:
        errors.append("section_count_below_expected")
    searchable_text = f"{extracted.rawText}\n{extracted.markdown}".casefold()
    for required in fixture.expectations.requiredText:
        if required.casefold() not in searchable_text:
            errors.append(f"missing_text:{required}")
    for expected in fixture.expectations.expectedSections:
        chunk = sections.get(expected.sectionRef)
        if not chunk:
            errors.append(f"missing_section:{expected.sectionRef}")
            continue
        metadata = chunk.get("metadata") or {}
        if expected.page is not None and metadata.get("pageStart") != expected.page:
            errors.append(f"wrong_page:{expected.sectionRef}")
        if expected.status and metadata.get("amendmentStatus") != expected.status:
            errors.append(f"wrong_status:{expected.sectionRef}")
    for value in fixture.expectations.tableCellValues:
        if not any(
            value.casefold() in str(cell).casefold()
            for table in extracted.tables
            for row in table.rows
            for cell in row
        ):
            errors.append(f"missing_table_cell:{value}")
    if fixture.expectations.scheduleRequired and not any(
        (chunk.get("metadata") or {}).get("schedule") for chunk in chunks
    ):
        errors.append("missing_schedule")
    if fixture.expectations.versionDate and not any(
        (chunk.get("metadata") or {}).get("versionDate")
        == fixture.expectations.versionDate
        for chunk in chunks
    ):
        errors.append("wrong_version_date")

    retrieval_results = [
        {
            "chunkId": str(index),
            "title": fixture.title,
            "sectionRef": chunk.get("sectionRef"),
            "sectionTitle": chunk.get("sectionTitle"),
            "text": chunk.get("chunkText"),
            "metadata": chunk.get("metadata"),
        }
        for index, chunk in enumerate(chunks)
    ]
    for question in fixture.questions:
        ranked = deterministic_rerank(question.question, retrieval_results)
        rank = next(
            (
                index
                for index, item in enumerate(ranked, start=1)
                if item.get("sectionRef") == question.expectedSectionRef
            ),
            None,
        )
        if rank is None or rank > question.expectedRank:
            errors.append(f"retrieval_rank:{question.expectedSectionRef}:{rank}")

    return FixtureReport(
        id=fixture.id,
        passed=not errors,
        errors=errors,
        pageCount=extracted.pageCount,
        sectionCount=len(sections),
        questionCount=len(fixture.questions),
    )


def evaluate_manifest(manifest_path: Path) -> GoldenReport:
    manifest = load_manifest(manifest_path)
    reports: list[FixtureReport] = []
    for fixture in manifest.fixtures:
        pdf_path = (manifest_path.parent / fixture.pdfPath).resolve()
        if not pdf_path.exists():
            reports.append(
                FixtureReport(
                    id=fixture.id,
                    passed=False,
                    errors=["pdf_missing"],
                    pageCount=0,
                    sectionCount=0,
                    questionCount=len(fixture.questions),
                )
            )
            continue
        data = pdf_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if fixture.sha256 and digest != fixture.sha256:
            reports.append(
                FixtureReport(
                    id=fixture.id,
                    passed=False,
                    errors=["sha256_mismatch"],
                    pageCount=0,
                    sectionCount=0,
                    questionCount=len(fixture.questions),
                )
            )
            continue
        reports.append(_evaluate_fixture(fixture, extract_pdf(data, pdf_path.name)))

    real_fixtures = [
        fixture for fixture in manifest.fixtures if fixture.fixtureType == "reviewed_real"
    ]
    jurisdictions = {fixture.jurisdiction for fixture in real_fixtures}
    total_questions = sum(len(fixture.questions) for fixture in real_fixtures)
    blockers: list[str] = []
    if len(real_fixtures) < 8:
        blockers.append("At least 8 reviewed real legal PDFs are required.")
    if len(jurisdictions) < 2 or "Cth" not in jurisdictions:
        blockers.append("The reviewed corpus must include Commonwealth and state legislation.")
    if any(len(fixture.questions) < 5 for fixture in real_fixtures):
        blockers.append("Each reviewed real fixture requires at least 5 citation questions.")
    if not any(fixture.expectations.tableCellValues for fixture in real_fixtures):
        blockers.append("The reviewed corpus requires at least one table-bearing document.")
    if not any(fixture.expectations.scheduleRequired for fixture in real_fixtures):
        blockers.append("The reviewed corpus requires at least one schedule-bearing document.")
    all_passed = bool(reports) and all(report.passed for report in reports)
    return GoldenReport(
        passed=all_passed,
        productionReady=all_passed and not blockers,
        realFixtureCount=len(real_fixtures),
        jurisdictionCount=len(jurisdictions),
        totalQuestions=total_questions,
        fixtureReports=reports,
        productionBlockers=blockers,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SafeSpeak legal golden evaluation.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-production", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate_manifest(args.manifest)
    rendered = report.model_dump_json(indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    if not report.passed or (args.require_production and not report.productionReady):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
