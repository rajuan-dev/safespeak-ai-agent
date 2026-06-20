import re
from datetime import date, datetime
from typing import Any

DATE_TOKEN = (
    r"(?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4}|\d{4}-\d{2}-\d{2}|"
    r"\d{1,2}/\d{1,2}/\d{4})"
)
VERSION_PATTERNS = [
    re.compile(
        rf"\b(?:as at|version date|compilation date|current to|"
        rf"reprint current from|version effective)\s*:?\s*({DATE_TOKEN})",
        re.I,
    ),
    re.compile(rf"\bversion\s+\d+(?:\.\d+)*\s+effective\s+({DATE_TOKEN})", re.I),
]
COMMENCEMENT_PATTERNS = [
    re.compile(rf"\b(?:commenced?|commencement date|commences?)\s*:?\s*({DATE_TOKEN})", re.I),
    re.compile(rf"\bwith effect from\s+({DATE_TOKEN})", re.I),
]
AMENDING_INSTRUMENT_RE = re.compile(
    r"\b(?:amended|inserted|substituted|repealed)\s+by\s+"
    r"([A-Z][A-Za-z0-9 ,.'()/-]{3,180}?(?:Act|Regulation|Rules?)\s+\d{4})",
    re.I,
)
EXTERNAL_REFERENCE_RE = re.compile(
    r"\b(?:section|sections|s)\.?\s+"
    r"([0-9]{1,4}[A-Za-z]?(?:\([0-9A-Za-z]+\))*)"
    r"(?:\s+(?:and|to|-)\s+([0-9]{1,4}[A-Za-z]?(?:\([0-9A-Za-z]+\))*))?"
    r"(?:\s+of\s+(?:the\s+)?([A-Z][A-Za-z0-9 ,.'()-]+?(?:Act|Regulation|Rules?)\s+\d{4}))?",
    re.I,
)
QUOTED_DEFINITION_RE = re.compile(
    r'(?:"([^"]+)"|“([^”]+)”)\s+(?:means|includes)\b',
    re.I,
)
PLAIN_DEFINITION_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9 -]{1,80}?)\s+(?:means|includes)\b",
    re.I | re.M,
)


def normalise_date(value: str | date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    for pattern in ("%d %B %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def first_date(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return normalise_date(match.group(1))
    return None


def detect_provision_status(text: str) -> tuple[str, str | None]:
    lowered = text.lower()
    instrument_match = AMENDING_INSTRUMENT_RE.search(text)
    instrument = instrument_match.group(1).strip(" .;,") if instrument_match else None
    if re.search(
        r"(?:^|\n)\s*(?:\[|\()?repealed(?:\]|\))?\b|"
        r"\brepealed by\b|\bceased to have effect\b",
        lowered,
    ):
        return "repealed", instrument
    if re.search(
        r"(?:^|\n)\s*(?:\[|\()?amended(?:\]|\))?\b|"
        r"\b(?:amended|inserted|substituted|modified) by\b",
        lowered,
    ):
        return "amended", instrument
    return "in_force", None


def extract_cross_references(text: str, current_act: str | None) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in EXTERNAL_REFERENCE_RE.finditer(text):
        act_name = (match.group(3) or current_act or "").strip()
        for section_ref in (match.group(1), match.group(2)):
            if not section_ref:
                continue
            key = (act_name.casefold(), section_ref.casefold())
            if key in seen:
                continue
            seen.add(key)
            references.append(
                {
                    "actName": act_name or None,
                    "sectionRef": section_ref,
                    "rawText": match.group(0),
                    "resolutionStatus": "unresolved",
                }
            )
    return references


def extract_defined_terms(text: str) -> list[str]:
    terms = {
        (match.group(1) or match.group(2)).strip()
        for match in QUOTED_DEFINITION_RE.finditer(text)
    }
    terms.update(match.group(1).strip() for match in PLAIN_DEFINITION_RE.finditer(text))
    return sorted(term for term in terms if term)


def source_version_date(source: dict[str, Any], document_text: str) -> str | None:
    metadata = source.get("metadata") or {}
    candidates = [
        metadata.get("effectiveDate"),
        metadata.get("versionDate"),
        source.get("lastUpdated"),
    ]
    for candidate in candidates:
        normalised = normalise_date(candidate)
        if normalised:
            return normalised
    return first_date(document_text, VERSION_PATTERNS)


def source_commencement_date(source: dict[str, Any], document_text: str) -> str | None:
    metadata = source.get("metadata") or {}
    for candidate in (metadata.get("commencementDate"), metadata.get("effectiveDate")):
        normalised = normalise_date(candidate)
        if normalised:
            return normalised
    return first_date(document_text, COMMENCEMENT_PATTERNS)


def build_structure_tree(chunks: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    root: dict[str, Any] = {
        "type": "source",
        "value": source.get("legislationName") or source.get("title"),
        "children": [],
    }
    nodes_by_key: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {(): root}
    for chunk in chunks:
        path = (chunk.get("metadata") or {}).get("hierarchyPath") or []
        parent = root
        key_parts: list[tuple[str, str]] = []
        for item in path:
            item_type = str(item.get("type", ""))
            item_value = str(item.get("value", ""))
            key_parts.append((item_type, item_value))
            key = tuple(key_parts)
            node = nodes_by_key.get(key)
            if node is None:
                node = {"type": item_type, "value": item_value, "children": []}
                parent["children"].append(node)
                nodes_by_key[key] = node
            parent = node
        parent.setdefault("chunks", []).append(
            {
                "chunkIndex": chunk.get("chunkIndex"),
                "sectionRef": chunk.get("sectionRef"),
                "pageStart": (chunk.get("metadata") or {}).get("pageStart"),
                "pageEnd": (chunk.get("metadata") or {}).get("pageEnd"),
                "status": (chunk.get("metadata") or {}).get("amendmentStatus"),
            }
        )
    return root
