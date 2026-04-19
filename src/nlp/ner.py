"""
ClinicalNER — rule-based named entity recognition for clinical notes.

Spec: specs/07-nlp-pipeline.md §3
Constitution: Article II.4 (no PHI in logs — entity text never logged)
              Article II.6 (conservative: skip low-confidence, short matches)
"""
from __future__ import annotations

import re

import structlog

from src.core.models.nlp import ClinicalEntity, EntityType, NoteSection, TemporalStatus

log = structlog.get_logger()

_MIN_ENTITY_LEN = 3

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Lab values: "creatinine 3.2 mg/dL", "hemoglobin 8.5", "WBC 14.5 K/uL"
_LAB_PATTERN = re.compile(
    r"\b(creatinine|hemoglobin|hgb|hematocrit|wbc|platelets?|sodium|potassium|"
    r"chloride|bicarbonate|bun|glucose|troponin|bnp|nt-probnp|lactate|albumin|"
    r"bilirubin|ast|alt|lipase|inr|pt|ptt)\s+"
    r"(\d+\.?\d*)\s*(?:mg/dl|g/dl|mmol/l|meq/l|k/ul|u/l|ng/ml|pg/ml|%)?",
    re.IGNORECASE,
)

# Vital signs: "BP 142/88", "HR 112", "O2 sat 88%", "temp 38.9"
_VITAL_PATTERN = re.compile(
    r"\b(bp|blood\s+pressure|hr|heart\s+rate|rr|respiratory\s+rate|"
    r"o2\s*sat|spo2|oxygen\s+saturation|temp(?:erature)?|map)\s*"
    r"(\d{2,3}(?:/\d{2,3})?(?:\.\d+)?)\s*(?:%|°[cf]|mmhg)?",
    re.IGNORECASE,
)

# Procedures (keyword list from high-value coding patterns)
_PROCEDURE_KEYWORDS: list[str] = [
    "intubation", "mechanical ventilation", "ventilator",
    "dialysis", "hemodialysis", "crrt", "continuous renal replacement",
    "central line", "arterial line", "swan-ganz",
    "thoracentesis", "paracentesis", "lumbar puncture",
    "transfusion", "blood transfusion",
    "bronchoscopy", "endoscopy", "colonoscopy",
    "pacemaker", "defibrillation", "cardioversion",
    "chest tube", "pericardiocentesis",
    "tracheostomy", "vasopressor",
]

# Disease/diagnosis keywords — high-revenue clinical entities from DISC-002
_DISEASE_KEYWORDS: list[str] = [
    # Sepsis spectrum
    "septic shock", "severe sepsis", "sepsis",
    "bacteremia", "fungemia",
    # Renal
    "acute kidney injury", "acute renal failure", "renal failure",
    "chronic kidney disease", "ckd",
    # Cardiac
    "acute on chronic systolic heart failure",
    "acute systolic heart failure",
    "acute diastolic heart failure",
    "heart failure", "chf", "cardiomyopathy",
    "atrial fibrillation", "atrial flutter",
    "myocardial infarction", "stemi", "nstemi",
    "coronary artery disease", "cad",
    # Respiratory
    "acute respiratory failure", "respiratory failure",
    "ards", "acute respiratory distress syndrome",
    "pneumonia", "copd exacerbation", "copd",
    "pulmonary embolism", "pe",
    # Neurological
    "metabolic encephalopathy", "encephalopathy",
    "delirium", "altered mental status",
    "ischemic stroke", "stroke", "tia",
    # Nutritional / metabolic
    "severe malnutrition", "malnutrition",
    "morbid obesity", "obesity",
    "diabetic ketoacidosis", "dka",
    "diabetes mellitus", "type 2 diabetes", "type 1 diabetes",
    "diabetes",
    # Hematologic
    "acute blood loss anemia", "anemia",
    "dvt", "deep vein thrombosis",
    # Wound
    "pressure ulcer", "decubitus",
    # Infectious
    "urinary tract infection", "uti",
    "cellulitis", "osteomyelitis",
    # Substance
    "alcohol withdrawal", "alcohol dependence",
]

# Build optimized regex for procedures and diseases (longest match first)
def _build_keyword_pattern(keywords: list[str]) -> re.Pattern[str]:
    sorted_kws = sorted(keywords, key=len, reverse=True)
    escaped = [re.escape(kw) for kw in sorted_kws]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


_PROCEDURE_RE = _build_keyword_pattern(_PROCEDURE_KEYWORDS)
_DISEASE_RE = _build_keyword_pattern(_DISEASE_KEYWORDS)


class ClinicalNER:
    """
    Extract clinical entities from section text using rule-based patterns.

    Returns list[ClinicalEntity] with verbatim text and character offsets.
    Entity text is always a substring of the input section_text.
    """

    def extract(self, text: str, section: NoteSection) -> list[ClinicalEntity]:
        if not text or not text.strip():
            return []

        entities: list[ClinicalEntity] = []
        occupied: set[tuple[int, int]] = set()

        self._extract_by_pattern(
            text, section, _LAB_PATTERN, EntityType.LAB_VALUE, 0.95, entities, occupied,
        )
        self._extract_by_pattern(
            text, section, _VITAL_PATTERN, EntityType.FINDING, 0.90, entities, occupied,
        )
        self._extract_keyword_matches(
            text, section, _PROCEDURE_RE, EntityType.PROCEDURE, 0.85, entities, occupied,
        )
        self._extract_keyword_matches(
            text, section, _DISEASE_RE, EntityType.DISEASE, 0.80, entities, occupied,
        )

        log.debug("ner_extraction_complete",
                  section=section.value,
                  entity_count=len(entities))
        return entities

    def _extract_by_pattern(
        self,
        text: str,
        section: NoteSection,
        pattern: re.Pattern[str],
        entity_type: EntityType,
        confidence: float,
        entities: list[ClinicalEntity],
        occupied: set[tuple[int, int]],
    ) -> None:
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            span = text[start:end]
            if len(span) < _MIN_ENTITY_LEN:
                continue
            if self._overlaps(start, end, occupied):
                continue
            occupied.add((start, end))
            entities.append(self._make_entity(span, start, end, entity_type, section, confidence))

    def _extract_keyword_matches(
        self,
        text: str,
        section: NoteSection,
        pattern: re.Pattern[str],
        entity_type: EntityType,
        confidence: float,
        entities: list[ClinicalEntity],
        occupied: set[tuple[int, int]],
    ) -> None:
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            span = text[start:end]
            if len(span) < _MIN_ENTITY_LEN:
                continue
            if self._overlaps(start, end, occupied):
                continue
            occupied.add((start, end))
            entities.append(self._make_entity(span, start, end, entity_type, section, confidence))

    @staticmethod
    def _overlaps(start: int, end: int, occupied: set[tuple[int, int]]) -> bool:
        return any(s < end and e > start for s, e in occupied)

    @staticmethod
    def _make_entity(
        text: str,
        start: int,
        end: int,
        entity_type: EntityType,
        section: NoteSection,
        confidence: float,
    ) -> ClinicalEntity:
        return ClinicalEntity(
            text=text,
            entity_type=entity_type,
            start_char=start,
            end_char=end,
            source_section=section,
            is_negated=False,
            negation_cue=None,
            temporal_status=TemporalStatus.CURRENT,
            temporal_cue=None,
            confidence=confidence,
        )
