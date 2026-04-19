"""
NLPPipeline — orchestrates section_parser → NER → negation → temporal.

Spec: specs/07-nlp-pipeline.md §6
Constitution: Article II.2 (entity.text is verbatim source for evidence_quote)
              Article II.4 (note text never logged — only counts and metrics)
              Article II.5 (graceful degradation at every step)
              Article II.6 (conservative: skip uncertain entities)
"""
from __future__ import annotations

import time

import structlog

from src.core.models.nlp import ClinicalEntity, NLPResult, NoteSection, TemporalStatus
from src.nlp.negation import NegationDetector
from src.nlp.ner import ClinicalNER
from src.nlp.section_parser import SectionParser
from src.nlp.temporal import TemporalClassifier

log = structlog.get_logger()


class NLPPipeline:
    """
    Full NLP pipeline for clinical note processing.

    Inject custom components for testing (dependency injection via constructor).
    All components must implement the same interface as their default classes.
    """

    def __init__(
        self,
        parser: SectionParser | None = None,
        ner: ClinicalNER | None = None,
        negation: NegationDetector | None = None,
        temporal: TemporalClassifier | None = None,
    ) -> None:
        self._parser = parser or SectionParser()
        self._ner = ner or ClinicalNER()
        self._negation = negation or NegationDetector()
        self._temporal = temporal or TemporalClassifier()

    def analyze(self, note_text: str) -> NLPResult:
        """
        Process a clinical note and return structured entities.

        Degrades gracefully: any component failure sets is_degraded=True
        and continues with available data. Never raises to caller.
        """
        start_time = time.time()
        is_degraded = False

        # Step 1: Parse sections
        sections: dict[NoteSection, str] = {}
        try:
            sections = self._parser.parse(note_text)
        except Exception as e:
            log.warning("section_parser_failed", error_type=type(e).__name__)
            sections = {NoteSection.UNKNOWN: note_text}
            is_degraded = True

        # Step 2: Extract entities per section
        all_entities: list[ClinicalEntity] = []
        try:
            for section, text in sections.items():
                if text.strip():
                    entities = self._ner.extract(text, section)
                    all_entities.extend(entities)
        except Exception as e:
            log.warning("ner_extraction_failed", error_type=type(e).__name__)
            is_degraded = True

        # Step 3: Apply negation detection
        enriched: list[ClinicalEntity] = []
        try:
            for entity in all_entities:
                section_text = sections.get(entity.source_section, note_text)
                neg_result = self._negation.check(entity.text, section_text)
                enriched.append(entity.model_copy(update={
                    "is_negated": neg_result.is_negated,
                    "negation_cue": neg_result.negation_cue,
                }))
        except Exception as e:
            log.warning("negation_detection_failed", error_type=type(e).__name__)
            enriched = all_entities
            is_degraded = True

        # Step 4: Apply temporal classification
        final_entities: list[ClinicalEntity] = []
        try:
            for entity in enriched:
                section_text = sections.get(entity.source_section, note_text)
                temp_result = self._temporal.classify(
                    entity.text, section_text, entity.source_section,
                )
                final_entities.append(entity.model_copy(update={
                    "temporal_status": temp_result.temporal_status,
                    "temporal_cue": temp_result.temporal_cue,
                }))
        except Exception as e:
            log.warning("temporal_classification_failed", error_type=type(e).__name__)
            final_entities = enriched
            is_degraded = True

        elapsed_ms = (time.time() - start_time) * 1000

        log.info(
            "nlp_pipeline_complete",
            entity_count=len(final_entities),
            section_count=len(sections),
            negated_count=sum(1 for e in final_entities if e.is_negated),
            historical_count=sum(
                1 for e in final_entities
                if e.temporal_status == TemporalStatus.HISTORICAL
            ),
            family_count=sum(
                1 for e in final_entities
                if e.temporal_status == TemporalStatus.FAMILY
            ),
            is_degraded=is_degraded,
            elapsed_ms=round(elapsed_ms, 2),
        )

        return NLPResult(
            entities=final_entities,
            sections={s.value: t for s, t in sections.items()},
            processing_time_ms=elapsed_ms,
            entity_count=len(final_entities),
            negated_count=sum(1 for e in final_entities if e.is_negated),
            historical_count=sum(
                1 for e in final_entities
                if e.temporal_status == TemporalStatus.HISTORICAL
            ),
            is_degraded=is_degraded,
        )
