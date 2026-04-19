"""
Unit tests for the NLP pipeline — BUILD-004.

Written BEFORE implementation (TDD red phase).
Spec: specs/07-nlp-pipeline.md
Constitution: Article II.2 (evidence citation), II.4 (no PHI in logs),
              II.5 (graceful degradation), II.6 (conservative defaults)

Run: uv run pytest tests/unit/test_nlp_pipeline.py -v
"""
import pytest

from src.core.models.nlp import (
    ClinicalEntity,
    EntityType,
    NLPResult,
    NoteSection,
    TemporalStatus,
)
from src.nlp.negation import NegationDetector
from src.nlp.ner import ClinicalNER
from src.nlp.pipeline import NLPPipeline
from src.nlp.section_parser import SectionParser
from src.nlp.temporal import TemporalClassifier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SOAP_NOTE = """
Chief Complaint: Shortness of breath

History of Present Illness:
Patient is a 68-year-old male presenting with acute shortness of breath.

Past Medical History:
Heart failure, diabetes mellitus type 2, CKD stage 3.

Physical Exam:
Vitals: BP 142/88, HR 112, O2 sat 88%, temp 37.2
Lungs: crackles bilaterally

Assessment:
Acute on chronic systolic heart failure.
Possible pneumonia.
Acute kidney injury — creatinine 3.2 mg/dL (baseline 1.1).

Plan:
IV furosemide 40mg. Blood cultures. Chest X-ray.
"""

SIMPLE_NOTE = "Sepsis with acute kidney injury. Creatinine 4.1 mg/dL."

NEGATED_NOTE = "No evidence of sepsis. Patient denies chest pain. Pneumonia ruled out."

HISTORICAL_NOTE = "History of diabetes mellitus. Prior DVT. Family history of coronary artery disease."


# ---------------------------------------------------------------------------
# 1. SectionParser
# ---------------------------------------------------------------------------

class TestSectionParser:
    def setup_method(self) -> None:
        self.parser = SectionParser()

    def test_soap_note_splits_into_known_sections(self) -> None:
        sections = self.parser.parse(SOAP_NOTE)
        assert NoteSection.SUBJECTIVE in sections
        assert NoteSection.OBJECTIVE in sections
        assert NoteSection.ASSESSMENT in sections
        assert NoteSection.PLAN in sections

    def test_history_section_identified(self) -> None:
        sections = self.parser.parse(SOAP_NOTE)
        assert NoteSection.HISTORY in sections

    def test_assessment_section_contains_diagnosis_text(self) -> None:
        sections = self.parser.parse(SOAP_NOTE)
        assessment_text = sections[NoteSection.ASSESSMENT]
        assert "heart failure" in assessment_text.lower()

    def test_note_with_no_headers_returns_unknown_section(self) -> None:
        sections = self.parser.parse(SIMPLE_NOTE)
        assert NoteSection.UNKNOWN in sections
        assert sections[NoteSection.UNKNOWN] == SIMPLE_NOTE

    def test_empty_note_returns_unknown_section(self) -> None:
        sections = self.parser.parse("")
        assert NoteSection.UNKNOWN in sections

    def test_section_text_is_not_empty(self) -> None:
        sections = self.parser.parse(SOAP_NOTE)
        for section_text in sections.values():
            assert len(section_text.strip()) > 0

    def test_plan_section_contains_plan_text(self) -> None:
        sections = self.parser.parse(SOAP_NOTE)
        plan_text = sections[NoteSection.PLAN]
        assert "furosemide" in plan_text.lower()

    def test_case_insensitive_header_matching(self) -> None:
        note = "ASSESSMENT:\nSepsis.\nPLAN:\nAntibiotics."
        sections = self.parser.parse(note)
        assert NoteSection.ASSESSMENT in sections
        assert NoteSection.PLAN in sections

    def test_hpi_maps_to_subjective(self) -> None:
        note = "HPI:\nPatient presents with fever.\nPhysical Exam:\nTemp 38.9"
        sections = self.parser.parse(note)
        assert NoteSection.SUBJECTIVE in sections

    def test_pmh_maps_to_history(self) -> None:
        note = "PMH:\nDiabetes, hypertension.\nAssessment:\nSepsis."
        sections = self.parser.parse(note)
        assert NoteSection.HISTORY in sections


# ---------------------------------------------------------------------------
# 2. ClinicalNER
# ---------------------------------------------------------------------------

class TestClinicalNER:
    def setup_method(self) -> None:
        self.ner = ClinicalNER()

    def test_extracts_sepsis_as_disease(self) -> None:
        text = "Patient has sepsis with bacteremia."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        types = [e.entity_type for e in entities]
        assert EntityType.DISEASE in types
        disease_texts = [e.text.lower() for e in entities if e.entity_type == EntityType.DISEASE]
        assert any("sepsis" in t for t in disease_texts)

    def test_extracts_aki_as_disease(self) -> None:
        text = "Acute kidney injury — creatinine elevated."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        disease_texts = [e.text.lower() for e in entities if e.entity_type == EntityType.DISEASE]
        assert any("kidney injury" in t or "aki" in t for t in disease_texts)

    def test_extracts_lab_value(self) -> None:
        text = "Creatinine 3.2 mg/dL. Hemoglobin 8.5 g/dL."
        entities = self.ner.extract(text, NoteSection.OBJECTIVE)
        types = [e.entity_type for e in entities]
        assert EntityType.LAB_VALUE in types

    def test_entity_offsets_are_valid_substrings(self) -> None:
        text = "Patient has sepsis and acute kidney injury."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        for entity in entities:
            assert entity.start_char >= 0
            assert entity.end_char <= len(text)
            assert entity.text == text[entity.start_char:entity.end_char]

    def test_empty_text_returns_empty_list(self) -> None:
        entities = self.ner.extract("", NoteSection.UNKNOWN)
        assert entities == []

    def test_no_duplicate_entities_at_same_offset(self) -> None:
        text = "Sepsis with acute kidney injury."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        positions = [(e.start_char, e.end_char) for e in entities]
        assert len(positions) == len(set(positions))

    def test_source_section_recorded(self) -> None:
        text = "Heart failure exacerbation."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        for entity in entities:
            assert entity.source_section == NoteSection.ASSESSMENT

    def test_entity_minimum_length_enforced(self) -> None:
        text = "No DVT."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        for entity in entities:
            assert len(entity.text) >= 3

    def test_heart_failure_extracted(self) -> None:
        text = "Acute on chronic systolic heart failure."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        disease_texts = [e.text.lower() for e in entities if e.entity_type == EntityType.DISEASE]
        assert any("heart failure" in t for t in disease_texts)

    def test_procedure_extracted(self) -> None:
        text = "Patient underwent dialysis and intubation."
        entities = self.ner.extract(text, NoteSection.PLAN)
        types = [e.entity_type for e in entities]
        assert EntityType.PROCEDURE in types

    def test_confidence_within_bounds(self) -> None:
        text = "Sepsis with respiratory failure."
        entities = self.ner.extract(text, NoteSection.ASSESSMENT)
        for entity in entities:
            assert 0.0 <= entity.confidence <= 1.0


# ---------------------------------------------------------------------------
# 3. NegationDetector
# ---------------------------------------------------------------------------

class TestNegationDetector:
    def setup_method(self) -> None:
        self.detector = NegationDetector()

    def test_no_evidence_of_negates_entity(self) -> None:
        section_text = "No evidence of sepsis."
        result = self.detector.check("sepsis", section_text)
        assert result.is_negated is True
        assert result.negation_cue is not None

    def test_denies_negates_entity(self) -> None:
        section_text = "Patient denies chest pain and shortness of breath."
        result = self.detector.check("chest pain", section_text)
        assert result.is_negated is True

    def test_ruled_out_negates_entity(self) -> None:
        section_text = "Pneumonia ruled out by chest X-ray."
        result = self.detector.check("Pneumonia", section_text)
        assert result.is_negated is True

    def test_without_negates_entity(self) -> None:
        section_text = "Patient is without fever or chills."
        result = self.detector.check("fever", section_text)
        assert result.is_negated is True

    def test_affirmed_entity_not_negated(self) -> None:
        section_text = "Patient has confirmed sepsis with bacteremia."
        result = self.detector.check("sepsis", section_text)
        assert result.is_negated is False

    def test_negation_does_not_cross_termination_token(self) -> None:
        # "no DVT" but then "but reports chest pain" — chest pain is NOT negated
        section_text = "No DVT, but patient reports chest pain."
        result = self.detector.check("chest pain", section_text)
        assert result.is_negated is False

    def test_not_present_in_post_context_negates(self) -> None:
        section_text = "Sepsis was not confirmed on further workup."
        result = self.detector.check("Sepsis", section_text)
        assert result.is_negated is True

    def test_entity_not_in_text_returns_not_negated(self) -> None:
        result = self.detector.check("sepsis", "Patient has heart failure.")
        assert result.is_negated is False

    def test_negative_for_negates(self) -> None:
        section_text = "Blood cultures were negative for bacteremia."
        result = self.detector.check("bacteremia", section_text)
        assert result.is_negated is True

    def test_absent_negates_entity(self) -> None:
        section_text = "Bowel sounds absent."
        result = self.detector.check("Bowel sounds", section_text)
        assert result.is_negated is True


# ---------------------------------------------------------------------------
# 4. TemporalClassifier
# ---------------------------------------------------------------------------

class TestTemporalClassifier:
    def setup_method(self) -> None:
        self.classifier = TemporalClassifier()

    def test_history_of_classifies_as_historical(self) -> None:
        section_text = "History of diabetes mellitus type 2."
        result = self.classifier.classify("diabetes mellitus", section_text, NoteSection.SUBJECTIVE)
        assert result.temporal_status == TemporalStatus.HISTORICAL

    def test_family_history_classifies_as_family(self) -> None:
        section_text = "Family history of coronary artery disease."
        result = self.classifier.classify("coronary artery disease", section_text, NoteSection.HISTORY)
        assert result.temporal_status == TemporalStatus.FAMILY

    def test_prior_classifies_as_historical(self) -> None:
        section_text = "Prior DVT in 2023."
        result = self.classifier.classify("DVT", section_text, NoteSection.HISTORY)
        assert result.temporal_status == TemporalStatus.HISTORICAL

    def test_current_entity_classifies_as_current(self) -> None:
        section_text = "Acute kidney injury, new onset this admission."
        result = self.classifier.classify("kidney injury", section_text, NoteSection.ASSESSMENT)
        assert result.temporal_status == TemporalStatus.CURRENT

    def test_history_section_defaults_to_historical(self) -> None:
        # In a HISTORY section, entities without any cue default to HISTORICAL
        section_text = "Diabetes. Hypertension."
        result = self.classifier.classify("Diabetes", section_text, NoteSection.HISTORY)
        assert result.temporal_status == TemporalStatus.HISTORICAL

    def test_assessment_section_defaults_to_current(self) -> None:
        section_text = "Sepsis. Acute kidney injury."
        result = self.classifier.classify("Sepsis", section_text, NoteSection.ASSESSMENT)
        assert result.temporal_status == TemporalStatus.CURRENT

    def test_hx_of_abbreviation_classified_historical(self) -> None:
        section_text = "H/o atrial fibrillation."
        result = self.classifier.classify("atrial fibrillation", section_text, NoteSection.HISTORY)
        assert result.temporal_status == TemporalStatus.HISTORICAL

    def test_family_overrides_historical(self) -> None:
        # When both family and historical cues present, FAMILY wins
        section_text = "Family history of prior MI."
        result = self.classifier.classify("MI", section_text, NoteSection.HISTORY)
        assert result.temporal_status == TemporalStatus.FAMILY

    def test_current_cue_overrides_historical_section(self) -> None:
        # Even in HISTORY section, "acute" cue → CURRENT
        section_text = "Acute respiratory failure, new onset."
        result = self.classifier.classify("respiratory failure", section_text, NoteSection.HISTORY)
        assert result.temporal_status == TemporalStatus.CURRENT

    def test_temporal_cue_recorded(self) -> None:
        section_text = "History of heart failure."
        result = self.classifier.classify("heart failure", section_text, NoteSection.SUBJECTIVE)
        assert result.temporal_cue is not None


# ---------------------------------------------------------------------------
# 5. NLPPipeline (Integration of all components)
# ---------------------------------------------------------------------------

class TestNLPPipeline:
    def setup_method(self) -> None:
        self.pipeline = NLPPipeline()

    def test_pipeline_returns_nlp_result(self) -> None:
        result = self.pipeline.analyze(SIMPLE_NOTE)
        assert isinstance(result, NLPResult)

    def test_pipeline_extracts_entities_from_soap_note(self) -> None:
        result = self.pipeline.analyze(SOAP_NOTE)
        assert result.entity_count > 0
        assert len(result.entities) == result.entity_count

    def test_pipeline_counts_negated_entities(self) -> None:
        result = self.pipeline.analyze(NEGATED_NOTE)
        assert result.negated_count > 0

    def test_pipeline_counts_historical_entities(self) -> None:
        result = self.pipeline.analyze(HISTORICAL_NOTE)
        assert result.historical_count > 0

    def test_pipeline_records_processing_time(self) -> None:
        result = self.pipeline.analyze(SIMPLE_NOTE)
        assert result.processing_time_ms > 0

    def test_empty_note_returns_empty_result(self) -> None:
        result = self.pipeline.analyze("")
        assert result.entity_count == 0
        assert result.is_degraded is False

    def test_entity_text_is_substring_of_source_note(self) -> None:
        """
        Article II.2 compliance: every entity.text must be a verbatim
        substring of the original note, enabling evidence_quote validation.
        """
        result = self.pipeline.analyze(SOAP_NOTE)
        for entity in result.entities:
            assert entity.text in SOAP_NOTE, (
                f"Entity '{entity.text}' not found in source note — "
                "violates Article II.2 evidence citation requirement"
            )

    def test_sections_recorded_in_result(self) -> None:
        result = self.pipeline.analyze(SOAP_NOTE)
        assert len(result.sections) > 0

    def test_degraded_result_on_parser_failure(self) -> None:
        """Article II.5: pipeline degrades gracefully when parser fails."""

        class BrokenParser:
            def parse(self, text: str) -> dict:
                raise RuntimeError("parser failed")

        pipeline = NLPPipeline(
            parser=BrokenParser(),  # type: ignore[arg-type]
        )
        result = pipeline.analyze(SIMPLE_NOTE)
        assert result.is_degraded is True
        assert isinstance(result, NLPResult)

    def test_degraded_result_on_ner_failure(self) -> None:
        """Article II.5: pipeline degrades gracefully when NER fails."""

        class BrokenNER:
            def extract(self, text: str, section: NoteSection) -> list[ClinicalEntity]:
                raise RuntimeError("ner failed")

        pipeline = NLPPipeline(ner=BrokenNER())  # type: ignore[arg-type]
        result = pipeline.analyze(SIMPLE_NOTE)
        assert result.is_degraded is True
        assert isinstance(result, NLPResult)

    def test_negated_entities_marked_is_negated_true(self) -> None:
        result = self.pipeline.analyze("No evidence of sepsis.")
        negated = [e for e in result.entities if e.is_negated]
        assert len(negated) > 0

    def test_historical_entities_have_historical_status(self) -> None:
        result = self.pipeline.analyze("History of diabetes mellitus.")
        historical = [e for e in result.entities if e.temporal_status == TemporalStatus.HISTORICAL]
        assert len(historical) > 0

    def test_family_history_entities_have_family_status(self) -> None:
        result = self.pipeline.analyze("Family history of coronary artery disease.")
        family = [e for e in result.entities if e.temporal_status == TemporalStatus.FAMILY]
        assert len(family) > 0
