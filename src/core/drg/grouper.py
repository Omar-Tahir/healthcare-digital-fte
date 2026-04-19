"""
DRG Grouper — calculates MS-DRG assignment and revenue impact.

Uses ICD10DataLoader for embedded CMS reference data:
  - _DRG_FAMILIES: code prefix → (MCC_drg, CC_drg, base_drg)
  - _DRG_WEIGHTS: DRG → relative weight
  - _BASE_RATE: national average Medicare base rate ($3,800)

calculate_drg: assigns DRG from principal + secondary codes (no LLM)
calculate_impact: revenue delta of adding one code to an existing claim

Constitution: II.6 (conservative — never overstate revenue potential),
              II.1 (no autonomous claims — DRGImpact is a suggestion, not a claim)
Spec: specs/01-coding-rules-engine.md §8
Skill: docs/skills/drg-optimization.md
"""
from __future__ import annotations

import structlog

from src.core.icd10.data_loader import ICD10DataLoader, _BASE_RATE, _DRG_WEIGHTS
from src.core.models.drg import DRGImpact, DRGResult

log = structlog.get_logger()

_UNKNOWN_DRG = "999"
_UNKNOWN_DESCRIPTION = "Unknown/Other"


class DRGGrouper:
    """
    Assigns MS-DRG and calculates revenue impact for ICD-10-CM code sets.

    Public interface:
      calculate_drg(principal, secondary) → DRGResult
      calculate_impact(current_codes, proposed_addition) → DRGImpact
    """

    def __init__(self) -> None:
        self._loader = ICD10DataLoader()

    def calculate_drg(
        self,
        principal: str,
        secondary: list[str] | None = None,
    ) -> DRGResult:
        """
        Assign MS-DRG based on principal diagnosis and secondary code set.

        Uses simplified grouper logic from ICD10DataLoader:
          1. Identify DRG family from principal code prefix
          2. Determine tier (MCC/CC/base) from highest severity in full code set
          3. Return DRGResult with weight and estimated payment
        """
        all_codes = [principal] + (secondary or [])
        drg, weight = self._loader.get_drg_for_code_set(all_codes)
        description = _UNKNOWN_DESCRIPTION if drg == _UNKNOWN_DRG else f"DRG {drg}"
        payment = weight * _BASE_RATE

        log.info(
            "drg_assigned",
            drg=drg,
            weight=weight,
            code_count=len(all_codes),
        )

        return DRGResult(
            drg=drg,
            description=description,
            weight=weight,
            estimated_payment=payment,
        )

    def calculate_impact(
        self,
        current_codes: list[str],
        proposed_addition: str,
    ) -> DRGImpact:
        """
        Calculate revenue impact of adding one code to an existing claim.

        Compares DRG assignment with and without the proposed code.
        DRGImpact model_validator auto-sets is_significant (>$1,000) and
        requires_compliance_review (>$5,000) flags.
        """
        current_drg, current_weight = self._loader.get_drg_for_code_set(current_codes)
        proposed_codes = current_codes + [proposed_addition]
        proposed_drg, proposed_weight = self._loader.get_drg_for_code_set(proposed_codes)

        revenue_difference = (proposed_weight - current_weight) * _BASE_RATE

        log.info(
            "drg_impact_calculated",
            current_drg=current_drg,
            proposed_drg=proposed_drg,
            revenue_difference=round(revenue_difference, 2),
        )

        return DRGImpact(
            current_drg=current_drg,
            current_drg_weight=current_weight,
            proposed_drg=proposed_drg,
            proposed_drg_weight=proposed_weight,
            revenue_difference=revenue_difference,
        )
