"""
ICD-10-CM reference data loader.

Phase 1: Minimum required reference data embedded as Python structures.
This is sufficient for compliance tests and Phase 1 accuracy benchmarks.

BUILD-008 replaces the embedded data with full CMS annual files loaded
from data/icd10/ (download script: scripts/download_icd10_data.sh).
The loader interface stays the same — BUILD-008 changes the data source.

Data sources used to compile embedded tables:
  - ICD-10-CM 2024 Tabular List (CMS public)
  - DISC-001: ICD-10 Official Guidelines research
  - docs/skills/icd10-coding-rules.md (Sections 1, 4)
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Excludes 1 pairs — bidirectional, stored as {code: {excluded_partners}}
# Source: ICD-10-CM 2024 Tabular List, Section I.A.12.a
# Adding both directions ensures order-independent detection
# ---------------------------------------------------------------------------
_EXCLUDES1_PAIRS: dict[str, frozenset[str]] = {
    # Heart failure specificity — unspecified EXCLUDES 1 specific types
    "I50.9": frozenset({
        "I50.20", "I50.21", "I50.22", "I50.23",
        "I50.30", "I50.31", "I50.32", "I50.33",
        "I50.40", "I50.41", "I50.42", "I50.43",
    }),
    "I50.20": frozenset({"I50.9"}),
    "I50.21": frozenset({"I50.9"}),
    "I50.22": frozenset({"I50.9"}),
    "I50.23": frozenset({"I50.9"}),
    "I50.30": frozenset({"I50.9"}),
    "I50.31": frozenset({"I50.9"}),
    "I50.32": frozenset({"I50.9"}),
    "I50.33": frozenset({"I50.9"}),
    "I50.40": frozenset({"I50.9"}),
    "I50.41": frozenset({"I50.9"}),
    "I50.42": frozenset({"I50.9"}),
    "I50.43": frozenset({"I50.9"}),
    # Diabetes type — Type 1 EXCLUDES 1 Type 2 (same patient cannot have both)
    "E10.9": frozenset({"E11.9", "E11.22", "E11.65", "E11.40"}),
    "E11.9": frozenset({"E10.9"}),
    "E11.22": frozenset({"E10.9", "E10.22"}),
    "E10.22": frozenset({"E11.22"}),
    "E11.65": frozenset({"E10.9"}),
    "E11.40": frozenset({"E10.9"}),
}

# ---------------------------------------------------------------------------
# Excludes 2 pairs — bidirectional, may coexist if both independently documented
# Source: ICD-10-CM 2024 Tabular List, Section I.A.12.b
# ---------------------------------------------------------------------------
_EXCLUDES2_PAIRS: dict[str, frozenset[str]] = {
    # Morbid obesity and obstructive sleep apnea
    "E66.01": frozenset({"G47.33"}),
    "G47.33": frozenset({"E66.01"}),
    # Hypertension and CKD (when NOT using combination I12/I13)
    "I10": frozenset({"N18.9", "N18.3", "N18.4", "N18.5"}),
    "N18.3": frozenset({"I10"}),
    "N18.4": frozenset({"I10"}),
    "N18.9": frozenset({"I10"}),
}

# ---------------------------------------------------------------------------
# Mandatory paired codes — {code: [required_prefix_or_code]}
# Source: ICD-10-CM "Use Additional Code" and "Code First" instructions
# ---------------------------------------------------------------------------
_MANDATORY_PAIRED: dict[str, list[str]] = {
    # E11.22: Use Additional Code for stage of CKD (N18.1-N18.6)
    "E11.22": ["N18."],
    # E11.65: Type 2 DM hyperglycemia — Code First underlying condition
    # G63: Polyneuropathy in diseases classified elsewhere — Code First
    "G63": ["E08.", "E09.", "E10.", "E11.", "E13."],
    # H36: Retinal disorder in diseases classified elsewhere — Code First
    "H36": ["E08.", "E09.", "E10.", "E11.", "E13."],
    # Sepsis with severe sepsis: R65.20 must accompany A40-A41
    "A41.01": ["R65."],
    "A41.9": [],  # R65.2x optional unless severe sepsis documented
    # Septic shock: must accompany sepsis code
    "R65.21": ["A40.", "A41.", "B37.", "G00.", "G03."],
}

# ---------------------------------------------------------------------------
# CC / MCC status — from CMS MS-DRG CC/MCC list
# Source: CMS FY2025 IPPS Final Rule — MS-DRG CC/MCC Designations
# ---------------------------------------------------------------------------
_CC_MCC_STATUS: dict[str, str] = {
    # MCC conditions (highest revenue impact)
    "N17.0": "MCC",   # AKI with tubular necrosis
    "N17.9": "MCC",   # AKI unspecified
    "A41.01": "MCC",  # Sepsis due to S. aureus
    "A41.9": "MCC",   # Sepsis unspecified
    "J96.01": "MCC",  # Acute respiratory failure with hypoxia
    "J96.00": "MCC",  # Acute respiratory failure unspecified
    "G93.41": "MCC",  # Metabolic encephalopathy
    "E43": "MCC",     # Unspecified severe protein-calorie malnutrition
    "I50.21": "MCC",  # Acute systolic CHF
    "I50.23": "MCC",  # Acute on chronic systolic CHF
    "I50.31": "MCC",  # Acute diastolic CHF
    "I50.33": "MCC",  # Acute on chronic diastolic CHF
    "I50.41": "MCC",  # Acute combined systolic and diastolic CHF
    "I50.43": "MCC",  # Acute on chronic combined CHF
    "F10.231": "MCC", # Alcohol dependence with withdrawal delirium
    # CC conditions
    "I50.9": "CC",    # CHF unspecified
    "I50.20": "CC",   # Unspecified systolic CHF
    "I50.22": "CC",   # Chronic systolic CHF
    "I50.30": "CC",   # Unspecified diastolic CHF
    "I50.32": "CC",   # Chronic diastolic CHF
    "I50.40": "CC",   # Unspecified combined CHF
    "I50.42": "CC",   # Chronic combined CHF
    "E11.22": "CC",   # T2DM with diabetic CKD
    "N18.3": "CC",    # CKD stage 3
    "N18.4": "CC",    # CKD stage 4
    "D62": "CC",      # Acute posthemorrhagic anemia
    "E66.01": "CC",   # Morbid obesity
    "J44.1": "CC",    # COPD acute exacerbation
    "G47.33": "CC",   # Obstructive sleep apnea
    "E87.1": "CC",    # Hyponatremia
    "I48.1": "CC",    # Persistent atrial fibrillation
}

# ---------------------------------------------------------------------------
# Simplified DRG grouper data
# Source: CMS FY2025 IPPS Final Rule — MS-DRG Relative Weights
# National average Medicare base rate: ~$3,800 (simplified)
# ---------------------------------------------------------------------------
_BASE_RATE: float = 3800.0

_DRG_WEIGHTS: dict[str, float] = {
    # Heart failure family (DRG 291-293)
    "291": 4.2234,   # HF + MCC
    "292": 2.5432,   # HF + CC
    "293": 1.0812,   # HF without CC/MCC
    # Sepsis family (DRG 870-872)
    "870": 5.1200,   # Sepsis + MCC
    "871": 2.5000,   # Sepsis + CC
    "872": 1.2342,   # Sepsis without CC/MCC
    # Pneumonia family (DRG 193-195)
    "193": 3.2156,   # Pneumonia + MCC
    "194": 1.8900,   # Pneumonia + CC
    "195": 1.0234,   # Pneumonia without CC/MCC
    # Simple discharge (default)
    "999": 0.9000,   # Unknown/other
}

# DRG family identification — code prefix → (MCC_drg, CC_drg, base_drg)
_DRG_FAMILIES: dict[str, tuple[str, str, str]] = {
    "I50.": ("291", "292", "293"),   # Heart failure
    "A40.": ("870", "871", "872"),   # Streptococcal sepsis
    "A41.": ("870", "871", "872"),   # Other sepsis
    "J18.": ("193", "194", "195"),   # Pneumonia, unspecified
    "J15.": ("193", "194", "195"),   # Bacterial pneumonia
    "J13.": ("193", "194", "195"),   # Pneumococcal pneumonia
}


class ICD10DataLoader:
    """
    Provides reference data lookups for the rules engine.

    All methods return immutable results — no state modification.
    Phase 1 uses embedded data; BUILD-008 replaces with CMS file loading.
    """

    def get_excludes1_partners(self, code: str) -> frozenset[str]:
        """Return codes with Excludes 1 relationship to this code."""
        return _EXCLUDES1_PAIRS.get(code, frozenset())

    def get_excludes2_partners(self, code: str) -> frozenset[str]:
        """Return codes with Excludes 2 relationship to this code."""
        return _EXCLUDES2_PAIRS.get(code, frozenset())

    def get_mandatory_paired_codes(self, code: str) -> list[str]:
        """Return required paired code prefixes for this code."""
        return _MANDATORY_PAIRED.get(code, [])

    def get_cc_mcc_status(self, code: str) -> str:
        """Return 'MCC', 'CC', or '' (non-CC) for this code."""
        return _CC_MCC_STATUS.get(code, "")

    def get_drg_for_code_set(self, codes: list[str]) -> tuple[str, float]:
        """
        Simplified DRG assignment: identify family from codes, then
        pick tier based on highest CC/MCC severity found in the set.
        Returns (drg_code, weight).
        """
        family = self._identify_drg_family(codes)
        tier = self._highest_cc_mcc_tier(codes)
        mcc_drg, cc_drg, base_drg = family
        if tier == "MCC":
            drg = mcc_drg
        elif tier == "CC":
            drg = cc_drg
        else:
            drg = base_drg
        return drg, _DRG_WEIGHTS.get(drg, _DRG_WEIGHTS["999"])

    def _identify_drg_family(self, codes: list[str]) -> tuple[str, str, str]:
        """Find the DRG family from the code prefixes present."""
        for code in codes:
            for prefix, family in _DRG_FAMILIES.items():
                if code.startswith(prefix):
                    return family
        return ("999", "999", "999")

    def _highest_cc_mcc_tier(self, codes: list[str]) -> str:
        """Return 'MCC', 'CC', or '' based on highest-severity code in set."""
        has_mcc = any(self.get_cc_mcc_status(c) == "MCC" for c in codes)
        if has_mcc:
            return "MCC"
        has_cc = any(self.get_cc_mcc_status(c) == "CC" for c in codes)
        if has_cc:
            return "CC"
        return ""
