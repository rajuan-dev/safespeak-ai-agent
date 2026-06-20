import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.models.extraction import ExtractedDocument, TextBlock
from app.services.legal_metadata import (
    COMMENCEMENT_PATTERNS,
    VERSION_PATTERNS,
    detect_provision_status,
    extract_cross_references,
    extract_defined_terms,
    first_date,
    source_commencement_date,
    source_version_date,
)

PART_RE = re.compile(r"^part\s+([0-9A-Za-z.-]+)\s*(.*)$", re.IGNORECASE)
DIVISION_RE = re.compile(r"^division\s+([0-9A-Za-z.-]+)\s*(.*)$", re.IGNORECASE)
SUBDIVISION_RE = re.compile(r"^subdivision\s+([0-9A-Za-z.-]+)\s*(.*)$", re.IGNORECASE)
SCHEDULE_RE = re.compile(r"^schedule\s+([0-9A-Za-z.-]+)\s*(.*)$", re.IGNORECASE)
SECTION_RE = re.compile(
    r"^(?:(?:section|s)\.?\s+)?([0-9]{1,4}[A-Za-z]?)\s+([A-Z][^\n]{2,240})$",
    re.IGNORECASE,
)
SUBSECTION_RE = re.compile(r"^\(([0-9]+[A-Za-z]?)\)\s*(.*)$")
PARAGRAPH_RE = re.compile(r"^\(([a-z])\)\s*(.*)$")
SUBPARAGRAPH_RE = re.compile(r"^\(([ivxlcdm]+)\)\s*(.*)$", re.IGNORECASE)
COMMENCEMENT_RE = re.compile(r"^(commencement|version|reprint|as at)\b", re.IGNORECASE)
CONTENTS_ENTRY_RE = re.compile(
    r"^\s*[0-9]{1,4}[A-Za-z]?(?:\([0-9A-Za-z]+\))*\s+.+\.{4,}\s*\d+\s*$"
)
RUNNING_HEADER_RE = re.compile(
    r"^(?:Authorised Version|Compilation No\.?|Compilation date:|"
    r"Prepared by the Office of Parliamentary Counsel)\b",
    re.I,
)
WEB_EXPORT_NOISE_RE = re.compile(
    r"^(?:https?://\S+|\d{1,2}/\d{1,2}/\d{4},\s+\d{1,2}:\d{2}\b.*|"
    r"\d+\s*/\s*\d+|--\s*\d+\s+of\s+\d+\s*--)$",
    re.I,
)
LEGISLATIVE_SOURCE_TYPES = {
    "act",
    "legislation",
    "regulation",
    "regulations",
    "rules",
    "statutory instrument",
}


@dataclass
class Hierarchy:
    part: str | None = None
    division: str | None = None
    subdivision: str | None = None
    schedule: str | None = None
    section: str | None = None
    section_heading: str | None = None
    subsection: str | None = None
    paragraph: str | None = None
    subparagraph: str | None = None

    def path(self) -> list[dict[str, str]]:
        values = [
            ("part", self.part),
            ("division", self.division),
            ("subdivision", self.subdivision),
            ("schedule", self.schedule),
            ("section", self.section),
            ("subsection", self.subsection),
            ("paragraph", self.paragraph),
            ("subparagraph", self.subparagraph),
        ]
        return [{"type": key, "value": value} for key, value in values if value]

    def section_ref(self) -> str | None:
        if not self.section:
            return None
        suffix = "".join(
            f"({value})"
            for value in (self.subsection, self.paragraph, self.subparagraph)
            if value
        )
        return f"{self.section}{suffix}"


@dataclass
class ChunkDraft:
    text_parts: list[str] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    hierarchy: Hierarchy = field(default_factory=Hierarchy)
    block_types: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.text_parts).strip()


def _clone_hierarchy(value: Hierarchy) -> Hierarchy:
    return Hierarchy(**value.__dict__)


def _non_content_pages(extracted: ExtractedDocument) -> set[int]:
    excluded: set[int] = set()
    endnotes_start: int | None = None
    for page in extracted.pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        contents_entries = sum(bool(CONTENTS_ENTRY_RE.match(line)) for line in lines)
        if (
            any(
                line.casefold()
                in {"contents", "table of contents", "table of provisions"}
                for line in lines[:12]
            )
            and contents_entries >= 3
        ):
            excluded.add(page.number)
        if endnotes_start is None and any(
            line.casefold() in {"endnotes", "endnotes about this compilation"}
            for line in lines[:15]
        ):
            endnotes_start = page.number
    if endnotes_start is not None:
        excluded.update(
            page.number for page in extracted.pages if page.number >= endnotes_start
        )
    return excluded


def _skip_line(line: str, source: dict[str, Any]) -> bool:
    stripped = line.strip()
    if (
        not stripped
        or RUNNING_HEADER_RE.match(stripped)
        or WEB_EXPORT_NOISE_RE.match(stripped)
    ):
        return True
    if CONTENTS_ENTRY_RE.match(stripped):
        return True
    if re.fullmatch(r"(?:[ivxlcdm]+|\d+)", stripped, re.I):
        return True
    title = str(source.get("legislationName") or source.get("title") or "").strip()
    return bool(title and stripped.casefold() == title.casefold())


def _classify(block: TextBlock, hierarchy: Hierarchy) -> str | None:
    text = block.text.strip()
    match = PART_RE.match(text)
    if match:
        hierarchy.part = match.group(1)
        hierarchy.division = hierarchy.subdivision = hierarchy.section = None
        hierarchy.subsection = hierarchy.paragraph = hierarchy.subparagraph = None
        return "part"
    match = DIVISION_RE.match(text)
    if match:
        hierarchy.division = match.group(1)
        hierarchy.subdivision = hierarchy.section = None
        hierarchy.subsection = hierarchy.paragraph = hierarchy.subparagraph = None
        return "division"
    match = SUBDIVISION_RE.match(text)
    if match:
        hierarchy.subdivision = match.group(1)
        hierarchy.section = None
        hierarchy.subsection = hierarchy.paragraph = hierarchy.subparagraph = None
        return "subdivision"
    match = SCHEDULE_RE.match(text)
    if match:
        hierarchy.schedule = match.group(1)
        hierarchy.part = hierarchy.division = hierarchy.subdivision = None
        hierarchy.section = hierarchy.subsection = hierarchy.paragraph = None
        hierarchy.subparagraph = None
        return "schedule"
    match = SECTION_RE.match(text)
    if match and (block.blockType == "heading" or block.isBold):
        hierarchy.section = match.group(1)
        hierarchy.section_heading = match.group(2).strip() or None
        hierarchy.subsection = hierarchy.paragraph = hierarchy.subparagraph = None
        return "section"
    match = SUBSECTION_RE.match(text)
    if match:
        hierarchy.subsection = match.group(1)
        hierarchy.paragraph = hierarchy.subparagraph = None
        return "subsection"
    match = SUBPARAGRAPH_RE.match(text)
    if match and hierarchy.paragraph:
        hierarchy.subparagraph = match.group(1)
        return "subparagraph"
    match = PARAGRAPH_RE.match(text)
    if match:
        hierarchy.paragraph = match.group(1)
        hierarchy.subparagraph = None
        return "paragraph"
    if COMMENCEMENT_RE.match(text):
        return "version"
    return None


def _split_oversized(draft: ChunkDraft) -> list[ChunkDraft]:
    settings = get_settings()
    if len(draft.text) <= settings.RAG_CHUNK_MAX_CHARS:
        return [draft]

    units: list[str] = []
    for text_part in draft.text_parts:
        if len(text_part) <= settings.RAG_CHUNK_TARGET_CHARS:
            units.append(text_part)
            continue
        sentences = [
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text_part)
            if item.strip()
        ]
        if len(sentences) == 1:
            sentences = [
                text_part[start : start + settings.RAG_CHUNK_TARGET_CHARS]
                for start in range(0, len(text_part), settings.RAG_CHUNK_TARGET_CHARS)
            ]
        units.extend(sentences)

    results: list[ChunkDraft] = []
    current: list[str] = []
    for unit in units:
        candidate = "\n".join([*current, unit]).strip()
        if current and len(candidate) > settings.RAG_CHUNK_TARGET_CHARS:
            results.append(
                ChunkDraft(
                    text_parts=current,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    hierarchy=_clone_hierarchy(draft.hierarchy),
                    block_types=draft.block_types,
                )
            )
            current = [unit]
        else:
            current.append(unit)
    if current:
        results.append(
            ChunkDraft(
                text_parts=current,
                page_start=draft.page_start,
                page_end=draft.page_end,
                hierarchy=_clone_hierarchy(draft.hierarchy),
                block_types=draft.block_types,
            )
        )
    return results


def chunk_extracted_document(
    extracted: ExtractedDocument,
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    hierarchy = Hierarchy()
    drafts: list[ChunkDraft] = []
    current: ChunkDraft | None = None
    excluded_pages = _non_content_pages(extracted)
    source_type = str(source.get("sourceType") or "").strip().casefold()
    is_legislative_document = source_type in LEGISLATIVE_SOURCE_TYPES

    def flush() -> None:
        nonlocal current
        if current and current.text:
            drafts.extend(_split_oversized(current))
        current = None

    for source_block in extracted.blocks:
        if source_block.pageStart in excluded_pages:
            continue
        if (
            not is_legislative_document
            and current is not None
            and source_block.pageStart > current.page_end
        ):
            flush()
        lines = [line.strip() for line in source_block.text.splitlines() if line.strip()]
        for line in lines:
            if _skip_line(line, source):
                continue
            block = source_block.model_copy(update={"text": line})
            heading_type = _classify(block, hierarchy) if is_legislative_document else None
            boundary = heading_type in {
                "part",
                "division",
                "subdivision",
                "schedule",
                "section",
                "subsection",
                "paragraph",
                "subparagraph",
            }
            if boundary:
                flush()
            if current is None:
                current = ChunkDraft(
                    page_start=block.pageStart,
                    page_end=block.pageEnd,
                    hierarchy=_clone_hierarchy(hierarchy),
                )
            current.text_parts.append(block.text)
            current.page_end = max(current.page_end, block.pageEnd)
            current.block_types.append(heading_type or block.blockType)

    flush()
    chunks: list[dict[str, Any]] = []
    document_version_date = source_version_date(source, extracted.rawText)
    document_commencement_date = source_commencement_date(source, extracted.rawText)
    tables_by_draft: dict[int, list[dict[str, Any]]] = {}
    for table in extracted.tables:
        candidates = [
            (draft_index, draft)
            for draft_index, draft in enumerate(drafts)
            if draft.page_start <= table.pageNumber <= draft.page_end
        ]
        if not candidates:
            continue
        target_index, _target = max(
            candidates,
            key=lambda candidate: (
                len(candidate[1].hierarchy.path()),
                candidate[0],
            ),
        )
        tables_by_draft.setdefault(target_index, []).append(table.model_dump(mode="python"))

    for index, draft in enumerate(drafts):
        section_ref = draft.hierarchy.section_ref()
        amendment_status, amending_instrument = detect_provision_status(draft.text)
        version_date = first_date(draft.text, VERSION_PATTERNS) or document_version_date
        commencement_date = (
            first_date(draft.text, COMMENCEMENT_PATTERNS) or document_commencement_date
        )
        tables = tables_by_draft.get(index, [])
        rendered_tables = "\n\n".join(
            f"[Structured table - page {table['pageNumber']}]\n{table['markdown']}"
            for table in tables
            if table.get("markdown")
        )
        chunk_text = (
            f"{draft.text}\n\n{rendered_tables}".strip() if rendered_tables else draft.text
        )
        act_name = source.get("legislationName") or source.get("title")
        metadata = {
            "legalSourceType": source.get("sourceType"),
            "actName": act_name,
            "sectionNumber": draft.hierarchy.section,
            "sectionHeading": draft.hierarchy.section_heading,
            "subsection": draft.hierarchy.subsection,
            "paragraph": draft.hierarchy.paragraph,
            "subparagraph": draft.hierarchy.subparagraph,
            "part": draft.hierarchy.part,
            "division": draft.hierarchy.division,
            "subdivision": draft.hierarchy.subdivision,
            "schedule": draft.hierarchy.schedule,
            "hierarchyPath": draft.hierarchy.path(),
            "pageStart": draft.page_start,
            "pageEnd": draft.page_end,
            "pageNumber": draft.page_start,
            "extractionMethod": extracted.extractionMethod,
            "documentSha256": extracted.sha256,
            "blockTypes": draft.block_types,
            "tables": tables,
            "amendmentStatus": amendment_status,
            "amendingInstrument": amending_instrument,
            "commencementDate": commencement_date,
            "versionDate": version_date,
            "crossReferences": extract_cross_references(chunk_text, act_name),
            "definedTerms": extract_defined_terms(chunk_text),
        }
        label_parts = [source.get("title", "Legal source")]
        if section_ref:
            label_parts.append(f"s {section_ref}")
        label_parts.append(f"p. {draft.page_start}")
        chunks.append(
            {
                "chunkIndex": index,
                "chunkText": chunk_text,
                "chunkHash": hashlib.sha256(chunk_text.encode()).hexdigest(),
                "sectionRef": section_ref,
                "sectionNumber": draft.hierarchy.section,
                "sectionTitle": draft.hierarchy.section_heading,
                "definedTerms": metadata["definedTerms"],
                "pageNumber": draft.page_start,
                "tokenCount": max(1, len(draft.text) // 4),
                "citationLabel": ", ".join(label_parts),
                "metadata": metadata,
            }
        )
    return chunks


def chunk_plain_text(text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    settings = get_settings()
    paragraphs = [item.strip() for item in re.split(r"\n{2,}", text) if item.strip()]
    chunks: list[dict[str, Any]] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > settings.RAG_CHUNK_TARGET_CHARS:
            chunks.append({"chunkText": current})
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append({"chunkText": current})

    output = []
    for index, chunk in enumerate(chunks):
        chunk_text = chunk["chunkText"]
        output.append(
            {
                "chunkIndex": index,
                "chunkText": chunk_text,
                "chunkHash": hashlib.sha256(chunk_text.encode()).hexdigest(),
                "tokenCount": max(1, len(chunk_text) // 4),
                "citationLabel": source.get("title", "Knowledge source"),
                "metadata": {"extractionMethod": "manual", "hierarchyPath": []},
            }
        )
    return output
