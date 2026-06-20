import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings

CITATION_RE = re.compile(r"\[SOURCE\s+(\d+)\]", re.I)
SECTION_RE = re.compile(
    r"\b(?:section|sections|s)\.?\s*([0-9]{1,4}[A-Za-z]?(?:\([0-9A-Za-z]+\))*)",
    re.I,
)
NUMBER_RE = re.compile(r"\b(?:\$\s*)?\d+(?:[,.]\d+)*(?:\s*(?:days?|years?|units?|%))?\b", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9]{3,}")
NOT_FOUND_RE = re.compile(r"\bnot found in the available (?:approved )?legal data\b", re.I)
STOPWORDS = {
    "also",
    "and",
    "are",
    "but",
    "can",
    "for",
    "from",
    "has",
    "have",
    "into",
    "its",
    "may",
    "must",
    "not",
    "that",
    "the",
    "their",
    "this",
    "under",
    "was",
    "were",
    "which",
    "with",
}


@dataclass
class VerificationResult:
    supported: bool
    errors: list[str] = field(default_factory=list)
    supported_sentences: int = 0
    total_sentences: int = 0


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in WORD_RE.findall(text)
        if token.casefold() not in STOPWORDS
    }


def _sentences(answer: str) -> list[str]:
    lines = [line.strip(" \t-*") for line in answer.splitlines() if line.strip()]
    output: list[str] = []
    for line in lines:
        output.extend(
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line)
            if item.strip()
        )
    return output


def _has_complete_provenance(source: dict[str, Any]) -> bool:
    metadata = source.get("metadata") or {}
    return all(
        (
            source.get("title"),
            source.get("sectionRef"),
            source.get("pageNumber") or metadata.get("pageStart"),
            source.get("versionDate") or metadata.get("versionDate"),
            source.get("citationUrl"),
        )
    )


def verify_grounded_answer(answer: str, sources: list[dict[str, Any]]) -> VerificationResult:
    if NOT_FOUND_RE.search(answer):
        return VerificationResult(supported=True)
    sentences = _sentences(answer)
    result = VerificationResult(supported=True, total_sentences=len(sentences))
    if not sentences:
        return VerificationResult(supported=False, errors=["empty_answer"])

    for sentence_index, sentence in enumerate(sentences, start=1):
        cited_numbers = [int(value) for value in CITATION_RE.findall(sentence)]
        if not cited_numbers:
            result.errors.append(f"sentence_{sentence_index}:missing_source_marker")
            continue
        cited_sources = [
            sources[number - 1] for number in cited_numbers if 1 <= number <= len(sources)
        ]
        if len(cited_sources) != len(cited_numbers):
            result.errors.append(f"sentence_{sentence_index}:invalid_source_marker")
            continue
        if get_settings().RAG_REQUIRE_COMPLETE_CITATIONS and not all(
            _has_complete_provenance(source) for source in cited_sources
        ):
            result.errors.append(f"sentence_{sentence_index}:incomplete_provenance")
            continue

        claim = CITATION_RE.sub("", sentence)
        claim_tokens = _tokens(claim)
        source_text = "\n".join(str(source.get("text") or "") for source in cited_sources)
        source_tokens = _tokens(source_text)
        support_score = len(claim_tokens & source_tokens) / max(1, len(claim_tokens))
        if support_score < get_settings().RAG_MIN_CLAIM_SUPPORT_SCORE:
            result.errors.append(f"sentence_{sentence_index}:weak_textual_support")
            continue

        source_sections = {
            str(source.get("sectionRef") or "").casefold() for source in cited_sources
        }
        unsupported_sections = [
            section
            for section in SECTION_RE.findall(claim)
            if section.casefold() not in source_sections
            and not any(
                value.startswith(section.split("(")[0].casefold()) for value in source_sections
            )
        ]
        if unsupported_sections:
            result.errors.append(f"sentence_{sentence_index}:unsupported_section")
            continue

        source_compact = re.sub(r"[\s,$]", "", source_text.casefold())
        numeric_claim = SECTION_RE.sub("", claim)
        unsupported_numbers = [
            value
            for value in NUMBER_RE.findall(numeric_claim)
            if re.sub(r"[\s,$]", "", value.casefold()) not in source_compact
            and value not in [str(number) for number in cited_numbers]
        ]
        if unsupported_numbers:
            result.errors.append(f"sentence_{sentence_index}:unsupported_number")
            continue
        result.supported_sentences += 1

    result.supported = not result.errors and result.supported_sentences == len(sentences)
    return result
