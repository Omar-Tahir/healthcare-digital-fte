"""
MIMIC-IV Data Loader

Loads discharge summaries and ICD-10 codes from MIMIC-IV CSV files.
Filters to ICD-10 admissions only (icd_version=10).
Formats codes with dots (e.g. "I5023" → "I50.23") for comparison
with coding agent output.

Constitution: Article II.4 — no PHI in any log message.
              subject_id is excluded from all logs; hadm_id is allowed
              (admission identifier, not PHI per MIMIC-IV Safe Harbor).
Spec: specs/07-mimic-benchmark.md §2, §3
ADR:  docs/adr/ADR-013-mimic-benchmark-design.md
"""
from __future__ import annotations

import csv
from pathlib import Path

import structlog
from pydantic import BaseModel

log = structlog.get_logger()

# Default filenames within the raw/ subdirectory
_DEFAULT_DISCHARGE = "discharge.csv"
_DEFAULT_DIAGNOSES = "diagnoses_icd.csv"


class MimicAdmission(BaseModel):
    """One MIMIC-IV hospital admission with note + gold ICD-10 codes."""

    hadm_id: str
    discharge_note: str        # full discharge summary text (not logged)
    gold_codes: list[str]      # ICD-10 codes with dots, ordered by seq_num
    principal_dx: str          # seq_num=1 code (with dots)
    total_code_count: int      # len(gold_codes)


class MimicLoader:
    """
    Loads MIMIC-IV admissions from CSV files in data_dir/raw/.

    Parameters
    ----------
    data_dir:
        Root directory for MIMIC data (e.g. Path("data/mimic")).
        Expects raw/{discharge.csv,diagnoses_icd.csv} inside.
    discharge_filename / diagnoses_filename:
        Override default filenames (used by tests with tmp_path fixtures).
    """

    def __init__(
        self,
        data_dir: Path,
        discharge_filename: str = _DEFAULT_DISCHARGE,
        diagnoses_filename: str = _DEFAULT_DIAGNOSES,
    ) -> None:
        self._data_dir = data_dir
        self._discharge_file = data_dir / discharge_filename
        self._diagnoses_file = data_dir / diagnoses_filename

    def load_admissions(self, sample_size: int = 100) -> list[MimicAdmission]:
        """
        Load up to sample_size ICD-10 admissions.

        Raises
        ------
        FileNotFoundError
            If either required CSV file is absent.
        """
        self._check_files_exist()
        gold_codes = self._load_gold_codes()
        notes = self._load_notes(set(gold_codes.keys()))
        return self._build_admissions(notes, gold_codes, sample_size)

    # ─── Private ─────────────────────────────────────────────────────────────

    def _check_files_exist(self) -> None:
        for path in (self._discharge_file, self._diagnoses_file):
            if not path.exists():
                raise FileNotFoundError(
                    f"MIMIC file not found: {path}. "
                    "Run scripts/download_mimic4.sh to download."
                )

    def _load_gold_codes(self) -> dict[str, list[tuple[int, str]]]:
        """
        Parse diagnoses_icd.csv.

        Returns dict: hadm_id → sorted list of (seq_num, formatted_code).
        Only includes admissions with icd_version=10.
        Never logs PHI (no patient names, DOBs, or clinical content).
        """
        codes: dict[str, list[tuple[int, str]]] = {}
        with open(self._diagnoses_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("icd_version", "").strip() != "10":
                    continue
                hadm_id = row["hadm_id"].strip()
                seq_num = int(row["seq_num"])
                raw_code = row["icd_code"].strip()
                formatted = _format_icd10_code(raw_code)
                codes.setdefault(hadm_id, []).append((seq_num, formatted))

        # Sort each admission's codes by seq_num
        return {h: sorted(c, key=lambda x: x[0]) for h, c in codes.items()}

    def _load_notes(
        self,
        target_hadm_ids: set[str],
    ) -> dict[str, str]:
        """
        Parse discharge.csv for admissions in target_hadm_ids.
        Returns dict: hadm_id → discharge note text.
        Only "Discharge summary" notes are included.
        """
        notes: dict[str, str] = {}
        with open(self._discharge_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                hadm_id = row.get("hadm_id", "").strip()
                note_type = row.get("note_type", "").strip()
                if hadm_id not in target_hadm_ids:
                    continue
                if note_type != "Discharge summary":
                    continue
                notes[hadm_id] = row.get("text", "")
        return notes

    def _build_admissions(
        self,
        notes: dict[str, str],
        gold_codes: dict[str, list[tuple[int, str]]],
        sample_size: int,
    ) -> list[MimicAdmission]:
        """
        Join notes with codes; return up to sample_size admissions.
        Skips admissions with empty notes or no codes.
        """
        admissions: list[MimicAdmission] = []
        for hadm_id, code_tuples in gold_codes.items():
            if len(admissions) >= sample_size:
                break
            note_text = notes.get(hadm_id, "")
            if not note_text.strip():
                continue
            codes = [c for _, c in code_tuples]
            principal = codes[0] if codes else ""
            admissions.append(MimicAdmission(
                hadm_id=hadm_id,
                discharge_note=note_text,
                gold_codes=codes,
                principal_dx=principal,
                total_code_count=len(codes),
            ))
            log.debug(
                "mimic_admission_loaded",
                hadm_id=hadm_id,           # admission ID — not PHI
                code_count=len(codes),
                # note_text intentionally omitted — PHI
                # subject_id intentionally omitted — PHI
            )
        return admissions


# ─── Code formatter ───────────────────────────────────────────────────────────

def _format_icd10_code(raw: str) -> str:
    """
    Add dots to a raw MIMIC ICD-10 code string.

    MIMIC stores codes without dots: "I5023" → "I50.23"
    ICD-10-CM dot placement rules:
      - Category (first 3 chars) + dot + remaining chars
      - Exception: codes with exactly 3 chars have no dot (e.g. "I10")

    Examples:
        "I10"    → "I10"
        "I509"   → "I50.9"
        "I5023"  → "I50.23"
        "N179"   → "N17.9"
        "E119"   → "E11.9"
        "S72001A"→ "S72.001A"
    """
    raw = raw.strip().upper()
    if len(raw) <= 3:
        return raw
    return f"{raw[:3]}.{raw[3:]}"
