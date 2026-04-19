"""
TemporalClassifier — determine whether a clinical entity is current,
historical, or family history.

Spec: specs/07-nlp-pipeline.md §5
Constitution: Article II.4 (no PHI in logs — entity text never logged)
              Article II.6 (conservative: default CURRENT so no coding missed)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from src.core.models.nlp import NoteSection, TemporalStatus

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Trigger pattern lists
# ---------------------------------------------------------------------------

_FAMILY_TRIGGERS: list[str] = [
    "family history of",
    "family hx of",
    "family hx",
    "fh:",
    "fhx:",
    "father with",
    "mother with",
    "sibling with",
    "parent with",
    "brother with",
    "sister with",
    "family history",
]

_HISTORICAL_TRIGGERS: list[str] = [
    "remote history of",
    "history of",
    "past history of",
    "past medical history",
    "medical history",
    "h/o",
    "hx of",
    "hx:",
    "pmh:",
    "prior history of",
    "prior",
    "previous",
    "formerly",
    "in the past",
    "past",
    "chronic",
    "old",
    "known",
    "established",
]

_CURRENT_TRIGGERS: list[str] = [
    "new onset",
    "newly diagnosed",
    "presenting with",
    "now with",
    "currently",
    "current",
    "active",
    "acute",
    "this admission",
    "today",
    "recent",
    "recently",
]

_PRE_CONTEXT_TOKENS = 8
_POST_CONTEXT_TOKENS = 4


def _build_pattern(triggers: list[str]) -> re.Pattern[str]:
    sorted_t = sorted(triggers, key=len, reverse=True)
    escaped = [re.escape(t) for t in sorted_t]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


_FAMILY_RE = _build_pattern(_FAMILY_TRIGGERS)
_HISTORICAL_RE = _build_pattern(_HISTORICAL_TRIGGERS)
_CURRENT_RE = _build_pattern(_CURRENT_TRIGGERS)


@dataclass
class TemporalResult:
    temporal_status: TemporalStatus
    temporal_cue: str | None


class TemporalClassifier:
    """
    Classify the temporal status of a clinical entity within its context.

    Priority: FAMILY > HISTORICAL > CURRENT (default).
    Section context provides default (HISTORY section → HISTORICAL).
    Explicit CURRENT trigger overrides section default.
    """

    def classify(
        self,
        entity_text: str,
        section_text: str,
        section: NoteSection,
    ) -> TemporalResult:
        text_lower = section_text.lower()
        entity_lower = entity_text.lower()
        m = re.search(r"\b" + re.escape(entity_lower) + r"\b", text_lower)
        if m is None:
            return self._default_for_section(section)
        pos = m.start()

        entity_end = pos + len(entity_text)
        pre_context = self._get_pre_context(section_text, pos)
        post_context = self._get_post_context(section_text, entity_end)

        # Priority 1: FAMILY (highest)
        cue = self._match(pre_context, _FAMILY_RE)
        if cue:
            return TemporalResult(temporal_status=TemporalStatus.FAMILY, temporal_cue=cue)

        # Priority 2: CURRENT explicit trigger (overrides historical section default)
        current_cue = self._match(pre_context, _CURRENT_RE) or self._match(post_context, _CURRENT_RE)
        if current_cue:
            return TemporalResult(temporal_status=TemporalStatus.CURRENT, temporal_cue=current_cue)

        # Priority 3: HISTORICAL trigger
        cue = self._match(pre_context, _HISTORICAL_RE) or self._match(post_context, _HISTORICAL_RE)
        if cue:
            return TemporalResult(temporal_status=TemporalStatus.HISTORICAL, temporal_cue=cue)

        # Priority 4: Section-based default
        return self._default_for_section(section)

    @staticmethod
    def _get_pre_context(text: str, entity_start: int) -> str:
        before = text[:entity_start]
        tokens = before.split()
        return " ".join(tokens[-_PRE_CONTEXT_TOKENS:])

    @staticmethod
    def _get_post_context(text: str, entity_end: int) -> str:
        after = text[entity_end:]
        tokens = after.split()
        return " ".join(tokens[:_POST_CONTEXT_TOKENS])

    @staticmethod
    def _match(context: str, pattern: re.Pattern[str]) -> str | None:
        m = pattern.search(context)
        return m.group() if m else None

    @staticmethod
    def _default_for_section(section: NoteSection) -> TemporalResult:
        if section == NoteSection.HISTORY:
            return TemporalResult(
                temporal_status=TemporalStatus.HISTORICAL,
                temporal_cue="history_section",
            )
        return TemporalResult(temporal_status=TemporalStatus.CURRENT, temporal_cue=None)
