"""
MCP tools — ICD-10-CM reference lookups.

Thin wrappers over ICD10DataLoader. Return structured dicts for agent
consumption; agents call these instead of injecting full code tables
into context (Skills + MCP pattern — see claude.md).

Constitution: II.4 (no PHI — these tools operate on codes, not patient data)
Skill: docs/skills/icd10-coding-rules.md
"""
from __future__ import annotations

from src.core.icd10.data_loader import ICD10DataLoader

_loader = ICD10DataLoader()


def mcp_icd10_lookup(code: str) -> dict[str, str]:
    """
    Look up CC/MCC status for a single ICD-10-CM code.

    Returns:
      {
        "code": str,
        "cc_mcc_status": "MCC" | "CC" | ""
      }
    """
    return {
        "code": code,
        "cc_mcc_status": _loader.get_cc_mcc_status(code),
    }


def mcp_excludes1_check(code_a: str, code_b: str) -> dict[str, object]:
    """
    Check whether two codes have an Excludes 1 relationship.

    Returns:
      {
        "code_a": str,
        "code_b": str,
        "has_conflict": bool
      }
    """
    partners = _loader.get_excludes1_partners(code_a)
    has_conflict = code_b in partners
    return {
        "code_a": code_a,
        "code_b": code_b,
        "has_conflict": has_conflict,
    }
