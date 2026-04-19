"""
MCP tools — DRG calculation and revenue impact.

Thin wrappers over DRGGrouper. Return structured dicts for agent
consumption. DRG calculation stays in the grouper; these tools
are the agent-facing interface.

Constitution: II.6 (conservative — never overstate revenue),
              II.1 (suggestions only — no autonomous claim submission)
Skill: docs/skills/drg-optimization.md
"""
from __future__ import annotations

from src.core.drg.grouper import DRGGrouper

_grouper = DRGGrouper()


def mcp_drg_calculate(codes: list[str]) -> dict[str, object]:
    """
    Calculate MS-DRG assignment for a code set.

    Args:
      codes: list of ICD-10-CM codes; first element treated as principal.

    Returns:
      {
        "drg": str,
        "description": str,
        "weight": float,
        "estimated_payment": float
      }
    """
    if not codes:
        return {"drg": "999", "description": "Unknown/Other", "weight": 0.9, "estimated_payment": 0.9 * 3800}

    principal = codes[0]
    secondary = codes[1:]
    result = _grouper.calculate_drg(principal=principal, secondary=secondary)
    return {
        "drg": result.drg,
        "description": result.description,
        "weight": result.weight,
        "estimated_payment": result.estimated_payment,
    }


def mcp_drg_impact(current_codes: list[str], proposed_addition: str) -> dict[str, object]:
    """
    Calculate revenue impact of adding one code to an existing claim.

    Returns:
      {
        "current_drg": str,
        "proposed_drg": str,
        "revenue_difference": float,
        "is_significant": bool,
        "requires_compliance_review": bool
      }
    """
    impact = _grouper.calculate_impact(
        current_codes=current_codes,
        proposed_addition=proposed_addition,
    )
    return {
        "current_drg": impact.current_drg,
        "proposed_drg": impact.proposed_drg,
        "current_drg_weight": impact.current_drg_weight,
        "proposed_drg_weight": impact.proposed_drg_weight,
        "revenue_difference": impact.revenue_difference,
        "is_significant": impact.is_significant,
        "requires_compliance_review": impact.requires_compliance_review,
    }
