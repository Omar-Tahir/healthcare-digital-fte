"""
src.core.models — single import point for all domain models.

Usage:
    from src.core.models import CodingSuggestion, DegradedResult, DRGImpact

All Pydantic v2 models. Constitution Article III.4.
"""
from src.core.models.audit import (
    AuditAction,
    AuditLogEntry,
    PHI_FIELD_NAMES,
    UserActionAuditEntry,
)
from src.core.models.cdi import (
    CDIAnalysisResult,
    CDIOpportunity,
    CDIOpportunityType,
    CDIQuery,
)
from src.core.models.coding import (
    CodingAnalysisResult,
    CodingSuggestion,
    CodingSuggestionSet,
    ConfidenceRoutingResult,
    GuidelineViolation,
    SpecificityResult,
    ValidationResult,
    ViolationSeverity,
)
from src.core.models.drg import (
    DRGComplianceResult,
    DRGImpact,
    DRGResult,
    DRGWeight,
)
from src.core.models.encounter import (
    CodingClass,
    EncounterClass,
    EncounterContext,
    INPATIENT_ENCOUNTER_CLASSES,
    OUTPATIENT_ENCOUNTER_CLASSES,
    PatientContext,
    UNCERTAINTY_QUALIFIERS,
    get_coding_class,
)
from src.core.models.fhir import (
    DegradedResult,
    FHIRCondition,
    FHIRDocumentReference,
    FHIREncounter,
    FHIRObservation,
    FHIRPatient,
    NoteContentType,
)
from src.core.models.guardrails import (
    ApprovalToken,
    GuardrailResult,
    GuardrailType,
    GuardrailWarning,
)
from src.core.models.nlp import (
    ClinicalEntity,
    EntityType,
    NLPResult,
    NoteSection,
    TemporalStatus,
)

__all__ = [
    # audit
    "AuditAction",
    "AuditLogEntry",
    "PHI_FIELD_NAMES",
    "UserActionAuditEntry",
    # cdi
    "CDIAnalysisResult",
    "CDIOpportunity",
    "CDIOpportunityType",
    "CDIQuery",
    # coding
    "CodingAnalysisResult",
    "CodingSuggestion",
    "CodingSuggestionSet",
    "ConfidenceRoutingResult",
    "GuidelineViolation",
    "SpecificityResult",
    "ValidationResult",
    "ViolationSeverity",
    # drg
    "DRGComplianceResult",
    "DRGImpact",
    "DRGResult",
    "DRGWeight",
    # encounter
    "CodingClass",
    "EncounterClass",
    "EncounterContext",
    "INPATIENT_ENCOUNTER_CLASSES",
    "OUTPATIENT_ENCOUNTER_CLASSES",
    "PatientContext",
    "UNCERTAINTY_QUALIFIERS",
    "get_coding_class",
    # fhir
    "DegradedResult",
    "FHIRCondition",
    "FHIRDocumentReference",
    "FHIREncounter",
    "FHIRObservation",
    "FHIRPatient",
    "NoteContentType",
    # guardrails
    "ApprovalToken",
    "GuardrailResult",
    "GuardrailType",
    "GuardrailWarning",
    # nlp
    "ClinicalEntity",
    "EntityType",
    "NLPResult",
    "NoteSection",
    "TemporalStatus",
]
