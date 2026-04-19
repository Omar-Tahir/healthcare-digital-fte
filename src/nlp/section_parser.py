"""
SectionParser — splits a free-text clinical note into named sections.

Spec: specs/07-nlp-pipeline.md §2
Constitution: Article II.4 (no PHI in logs — section content never logged)
              Article II.5 (graceful degradation — unknown sections → UNKNOWN)
"""
from __future__ import annotations

import re
import structlog

from src.core.models.nlp import NoteSection

log = structlog.get_logger()

# Maps NoteSection enum values to regex patterns matching their headers.
# Patterns are case-insensitive and match common clinical documentation styles.
_SECTION_PATTERNS: dict[NoteSection, list[str]] = {
    NoteSection.SUBJECTIVE: [
        r"chief\s+complaint",
        r"history\s+of\s+present\s+illness",
        r"\bhpi\b",
        r"\bsubjective\b",
        r"\bcc\s*:",
    ],
    NoteSection.OBJECTIVE: [
        r"physical\s+exam",
        r"\bvitals?\b",
        r"\blabs?\b",
        r"\bobjective\b",
        r"\bexam\b",
        r"\bpe\s*:",
    ],
    NoteSection.ASSESSMENT: [
        r"\bassessment\b",
        r"\bimpression\b",
        r"\bdiagnosis\b",
        r"\ba/p\b",
        r"\ba\s*:",
    ],
    NoteSection.PLAN: [
        r"\bplan\b",
        r"\btreatment\b",
        r"\borders\b",
        r"\bp\s*:",
    ],
    NoteSection.HISTORY: [
        r"past\s+medical\s+history",
        r"\bpmh\b",
        r"social\s+history",
        r"family\s+history",
        r"medical\s+history",
        r"past\s+history",
    ],
}

_MAX_SECTION_CHARS = 10_000


def _build_combined_pattern() -> re.Pattern[str]:
    """Build a single regex matching any known section header."""
    all_patterns = []
    for patterns in _SECTION_PATTERNS.values():
        all_patterns.extend(patterns)
    joined = "|".join(f"(?:{p})" for p in all_patterns)
    return re.compile(rf"^(?:{joined})\s*:?\s*$", re.IGNORECASE | re.MULTILINE)


def _match_section(header_text: str) -> NoteSection:
    """Return the NoteSection for a matched header line."""
    lower = header_text.lower().strip().rstrip(":")
    for section, patterns in _SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower, re.IGNORECASE):
                return section
    return NoteSection.UNKNOWN


class SectionParser:
    """
    Splits a clinical note into named sections using header detection.

    Returns dict[NoteSection, str]. Sections with no content are omitted.
    If no headers are found, returns {NoteSection.UNKNOWN: full_note_text}.
    """

    def __init__(self) -> None:
        self._header_re = _build_combined_pattern()

    def parse(self, note_text: str) -> dict[NoteSection, str]:
        if not note_text or not note_text.strip():
            return {NoteSection.UNKNOWN: note_text}

        matches = list(self._header_re.finditer(note_text))

        if not matches:
            return {NoteSection.UNKNOWN: note_text}

        sections: dict[NoteSection, list[str]] = {}
        boundaries = [(m.start(), m.end(), m.group()) for m in matches]

        # Text before the first header → UNKNOWN
        pre_header = note_text[: boundaries[0][0]].strip()
        if pre_header:
            sections.setdefault(NoteSection.UNKNOWN, []).append(pre_header)

        for i, (start, end, header) in enumerate(boundaries):
            section = _match_section(header)
            next_start = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(note_text)
            body = note_text[end:next_start].strip()
            if body:
                sections.setdefault(section, []).append(body)

        result: dict[NoteSection, str] = {}
        for section, parts in sections.items():
            text = "\n".join(parts)
            if len(text) > _MAX_SECTION_CHARS:
                log.warning("section_truncated",
                            section=section.value,
                            original_length=len(text))
                text = text[:_MAX_SECTION_CHARS]
            result[section] = text

        log.debug("section_parse_complete", section_count=len(result))
        return result
