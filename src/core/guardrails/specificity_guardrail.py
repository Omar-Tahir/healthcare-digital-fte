"""
Specificity Guardrail — G-SOFT-003 (conservative defaults).

Enforces constitution Article II.6: When documentation does not support
a higher-specificity code, downgrade to the lower-specificity version
and generate a CDI query.

Upcoding risk (FCA liability) is catastrophically worse than undercoding
risk. Conservative default = lower specificity + CDI query.

The specificity downgrade map covers common HF codes where acuity
(acute vs. chronic) or type (systolic vs. diastolic) is not documented.

Constitution: Article II.6
Spec: specs/03-compliance-guardrail-architecture.md §1 G-SOFT-003
"""
from __future__ import annotations

import structlog

from src.core.models.coding import CodingSuggestion, SpecificityResult

log = structlog.get_logger()

# Maps higher-specificity code → lower-specificity fallback
# Only one direction: the more specific (often higher-revenue) code
# gets downgraded when documentation doesn't support it.
_SPECIFICITY_DOWNGRADE_MAP: dict[str, str] = {
    # Systolic HF: acute → unspecified (acuity not documented)
    "I50.21": "I50.20",  # Acute systolic CHF → Unspecified systolic CHF
    "I50.23": "I50.22",  # Acute on chronic systolic CHF → Chronic systolic CHF
    "I50.31": "I50.30",  # Acute diastolic CHF → Unspecified diastolic CHF
    "I50.33": "I50.32",  # Acute on chronic diastolic CHF → Chronic diastolic CHF
    "I50.41": "I50.40",  # Acute combined CHF → Unspecified combined CHF
    "I50.43": "I50.42",  # Acute on chronic combined CHF → Chronic combined CHF
}

_CDI_CATEGORY_MAP: dict[str, str] = {
    "I50.21": "severity_upgrade",
    "I50.23": "severity_upgrade",
    "I50.31": "severity_upgrade",
    "I50.33": "severity_upgrade",
    "I50.41": "severity_upgrade",
    "I50.43": "severity_upgrade",
}


def apply_conservative_specificity(
    suggestion: CodingSuggestion,
    documentation_supports_acuity: bool,
) -> SpecificityResult:
    """
    Apply conservative specificity rule (Article II.6).

    If documentation_supports_acuity=False and the suggested code is
    a higher-specificity code with a lower-specificity fallback:
    → Downgrade to lower-specificity code
    → Set cdi_query_required=True

    If the code is not in the downgrade map, or documentation supports it:
    → Keep original code
    → cdi_query_required=False
    """
    if not documentation_supports_acuity and suggestion.code in _SPECIFICITY_DOWNGRADE_MAP:
        downgraded = _SPECIFICITY_DOWNGRADE_MAP[suggestion.code]
        cdi_category = _CDI_CATEGORY_MAP.get(suggestion.code, "specificity_upgrade")

        log.info(
            "conservative_specificity_applied",
            original_code=suggestion.code,
            downgraded_code=downgraded,
            reason="documentation_does_not_support_acuity",
        )

        return SpecificityResult(
            selected_code=downgraded,
            original_code=suggestion.code,
            cdi_query_required=True,
            cdi_query_category=cdi_category,
        )

    return SpecificityResult(
        selected_code=suggestion.code,
        original_code=suggestion.code,
        cdi_query_required=False,
        cdi_query_category=None,
    )
