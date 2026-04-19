"""
DRG Grouper + MCP Tools Unit Tests — BUILD-008.
Written BEFORE implementation (TDD red phase, constitution Article I.2).

Tests verify:
  - DRGGrouper.calculate_drg: HF family (DRG 291/292/293), sepsis (870/871/872)
  - DRGGrouper.calculate_impact: revenue delta between two DRG tiers
  - MCP tool wrappers: icd10_lookup, excludes1_check, drg_calculate, drg_impact

No API calls — all tests are pure Python.
Constitution: II.6 (conservative), II.4 (no PHI in logs)
Spec: specs/01-coding-rules-engine.md §8
"""
from __future__ import annotations

import pytest

from src.core.drg.grouper import DRGGrouper
from src.core.models.drg import DRGImpact, DRGResult
from src.mcp.drg_tools import mcp_drg_calculate, mcp_drg_impact
from src.mcp.icd10_tools import mcp_excludes1_check, mcp_icd10_lookup


class TestDRGGrouper:
    @pytest.fixture
    def grouper(self) -> DRGGrouper:
        return DRGGrouper()

    def test_heart_failure_without_mcc_gives_drg_292(
        self, grouper: DRGGrouper
    ) -> None:
        """
        HF principal (I50.9 = CC) with no MCC secondary → DRG 292 (HF + CC).
        I50.9 itself is CC status → tier is CC → DRG 292.
        DRG 293 would require a HF code with no CC/MCC designation at all.

        DRG 292 weight = 2.5432, payment = 2.5432 × 3800 ≈ $9,664.
        """
        result = grouper.calculate_drg(
            principal="I50.9",
            secondary=[],
        )
        assert isinstance(result, DRGResult)
        assert result.drg == "292"
        assert result.weight == pytest.approx(2.5432)

    def test_heart_failure_with_mcc_gives_drg_291(
        self, grouper: DRGGrouper
    ) -> None:
        """
        HF principal (I50.9) + MCC secondary (N17.9 = AKI, MCC status) → DRG 291.

        Per DISC-002 CDI-SEV-001: adding AKI to HF claim upgrades DRG 293→291.
        DRG 291 weight = 4.2234.
        """
        result = grouper.calculate_drg(
            principal="I50.9",
            secondary=["N17.9"],  # N17.9 is MCC
        )
        assert isinstance(result, DRGResult)
        assert result.drg == "291"
        assert result.weight == pytest.approx(4.2234)

    def test_sepsis_organism_specificity_affects_drg(
        self, grouper: DRGGrouper
    ) -> None:
        """
        Sepsis family DRG 870/871/872.
        A41.9 (sepsis unspecified) with no secondary CC/MCC.
        A41.9 itself is MCC → DRG 870.
        """
        result = grouper.calculate_drg(
            principal="A41.9",
            secondary=[],
        )
        assert isinstance(result, DRGResult)
        assert result.drg == "870"  # A41.9 = MCC → top tier

    def test_drg_impact_calculated_correctly(
        self, grouper: DRGGrouper
    ) -> None:
        """
        Adding N17.9 (MCC) to a HF claim (I50.9 = CC → DRG 292) upgrades to DRG 291.
        Revenue delta = (4.2234 - 2.5432) × 3800 ≈ $6,384.
        Impact is significant (>$1,000) and requires compliance review (>$5,000).

        Per DISC-002 CDI-SEV-001: AKI documentation unlocks MCC tier → top DRG family.
        """
        impact = grouper.calculate_impact(
            current_codes=["I50.9"],
            proposed_addition="N17.9",
        )
        assert isinstance(impact, DRGImpact)
        assert impact.current_drg == "292"
        assert impact.proposed_drg == "291"
        assert impact.revenue_difference == pytest.approx(
            (4.2234 - 2.5432) * 3800, rel=1e-3
        )
        assert impact.is_significant is True
        assert impact.requires_compliance_review is True


class TestMCPICD10Tools:
    def test_mcp_icd10_lookup_returns_valid_code(self) -> None:
        """
        mcp_icd10_lookup returns a dict with code, cc_mcc_status.
        N17.9 is a known MCC code.
        """
        result = mcp_icd10_lookup("N17.9")
        assert isinstance(result, dict)
        assert result["code"] == "N17.9"
        assert result["cc_mcc_status"] == "MCC"

    def test_mcp_icd10_lookup_unknown_code_returns_empty_status(self) -> None:
        """
        Unknown code → cc_mcc_status is empty string (not CC or MCC).
        """
        result = mcp_icd10_lookup("Z99.999")
        assert isinstance(result, dict)
        assert result["code"] == "Z99.999"
        assert result["cc_mcc_status"] == ""

    def test_mcp_excludes1_check_detects_pair(self) -> None:
        """
        I50.9 and I50.21 form an Excludes 1 pair — cannot be billed together.
        """
        result = mcp_excludes1_check("I50.9", "I50.21")
        assert isinstance(result, dict)
        assert result["has_conflict"] is True
        assert "I50.9" in result["code_a"] or "I50.9" in result["code_b"]

    def test_mcp_excludes1_check_no_conflict(self) -> None:
        """
        N17.9 and I50.21 have no Excludes 1 relationship.
        """
        result = mcp_excludes1_check("N17.9", "I50.21")
        assert isinstance(result, dict)
        assert result["has_conflict"] is False


class TestMCPDRGTools:
    def test_mcp_drg_calculate(self) -> None:
        """
        mcp_drg_calculate returns DRG assignment as a dict.
        """
        result = mcp_drg_calculate(["I50.9"])
        assert isinstance(result, dict)
        assert "drg" in result
        assert "weight" in result
        assert "estimated_payment" in result
        assert result["drg"] == "292"  # I50.9 is CC → DRG 292 (HF + CC)

    def test_mcp_drg_impact_calculates_revenue_delta(self) -> None:
        """
        mcp_drg_impact returns impact dict including revenue_difference.
        Adding N17.9 to HF claim is significant and requires compliance review.
        """
        result = mcp_drg_impact(current_codes=["I50.9"], proposed_addition="N17.9")
        assert isinstance(result, dict)
        assert "revenue_difference" in result
        assert result["revenue_difference"] > 5000
        assert result["requires_compliance_review"] is True
