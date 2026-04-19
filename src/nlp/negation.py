"""
NegationDetector — NegEx-style rule-based negation detection.

Spec: specs/07-nlp-pipeline.md §4
Constitution: Article II.4 (no PHI in logs — entity text never logged)
              Article II.6 (conservative: default is_negated=False)

Based on: Chapman et al. (2001), "A Simple Algorithm for Identifying
Negated Findings and Diseases in Discharge Summaries."
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

log = structlog.get_logger()

# Tokens that terminate the negation context window
_TERMINATION_TOKENS: set[str] = {
    "but", "however", "although", "except", "despite", "though",
    "yet", "whereas", "while", "still",
}
_TERMINATION_PUNCT = re.compile(r"[,;.]")

# Pre-negation triggers: appear BEFORE the entity
_PRE_NEG_TRIGGERS: list[str] = [
    "no evidence of",
    "no sign of",
    "no signs of",
    "no history of",
    "no complaint of",
    "negative for",
    "free of",
    "absence of",
    "without",
    "denies",
    "denied",
    "not",
    "never",
    "nor",
    "neither",
    "cannot",
    "can't",
    "absent",
    "no",
]

# Post-negation triggers: appear AFTER the entity
_POST_NEG_TRIGGERS: list[str] = [
    "ruled out",
    "was ruled out",
    "not confirmed",
    "not found",
    "not detected",
    "not present",
    "was negative",
    "not seen",
    "not identified",
    "absent",
    "was absent",
    "not appreciated",
]

# Build sorted regex for triggers (longest first to avoid partial matches)
def _build_trigger_pattern(triggers: list[str]) -> re.Pattern[str]:
    sorted_t = sorted(triggers, key=len, reverse=True)
    escaped = [re.escape(t) for t in sorted_t]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


_PRE_NEG_RE = _build_trigger_pattern(_PRE_NEG_TRIGGERS)
_POST_NEG_RE = _build_trigger_pattern(_POST_NEG_TRIGGERS)

_CONTEXT_WINDOW_TOKENS = 6


@dataclass
class NegationResult:
    is_negated: bool
    negation_cue: str | None


class NegationDetector:
    """
    Determine whether a clinical entity is negated in its context.

    Context window: 6 tokens before and after the entity span.
    Negation context is terminated by punctuation or adversative conjunctions.
    Default: is_negated=False (conservative per Article II.6).
    """

    def check(self, entity_text: str, section_text: str) -> NegationResult:
        # Case-insensitive entity search
        entity_lower = entity_text.lower()
        text_lower = section_text.lower()
        pos = text_lower.find(entity_lower)
        if pos == -1:
            return NegationResult(is_negated=False, negation_cue=None)

        entity_end = pos + len(entity_text)
        pre_context = self._extract_pre_context(section_text, pos)
        post_context = self._extract_post_context(section_text, entity_end)

        cue = self._find_pre_trigger(pre_context)
        if cue:
            log.debug("negation_detected", cue=cue)
            return NegationResult(is_negated=True, negation_cue=cue)

        cue = self._find_post_trigger(post_context)
        if cue:
            log.debug("negation_detected", cue=cue)
            return NegationResult(is_negated=True, negation_cue=cue)

        return NegationResult(is_negated=False, negation_cue=None)

    def _extract_pre_context(self, text: str, entity_start: int) -> str:
        """Extract text before the entity, stopping at termination boundaries."""
        before = text[:entity_start]
        # Work right-to-left: stop at termination punct or token
        window = self._trim_to_window(before, reverse=True)
        return window

    def _extract_post_context(self, text: str, entity_end: int) -> str:
        """Extract text after the entity, stopping at termination boundaries."""
        after = text[entity_end:]
        window = self._trim_to_window(after, reverse=False)
        return window

    def _trim_to_window(self, text: str, reverse: bool) -> str:
        """
        Trim text to at most _CONTEXT_WINDOW_TOKENS tokens,
        stopping at any termination punct or adversative conjunction.
        """
        if reverse:
            text = text[::-1]

        result_chars: list[str] = []
        token_count = 0
        i = 0
        while i < len(text):
            char = text[i]
            # Check for termination punctuation
            if _TERMINATION_PUNCT.match(char):
                break
            # Accumulate token chars
            result_chars.append(char)
            # Check word boundaries
            if char == " ":
                word = "".join(result_chars).strip()
                if reverse:
                    word = word[::-1]
                for tok in word.split():
                    if tok.lower() in _TERMINATION_TOKENS:
                        # Remove the termination token from context
                        result_chars = result_chars[: -(len(tok) + 1)]
                        return ("".join(result_chars)[::-1] if reverse
                                else "".join(result_chars))
                token_count += 1
                if token_count >= _CONTEXT_WINDOW_TOKENS:
                    break
            i += 1

        window = "".join(result_chars)
        return window[::-1] if reverse else window

    @staticmethod
    def _find_pre_trigger(context: str) -> str | None:
        m = _PRE_NEG_RE.search(context)
        return m.group() if m else None

    @staticmethod
    def _find_post_trigger(context: str) -> str | None:
        m = _POST_NEG_RE.search(context)
        return m.group() if m else None
