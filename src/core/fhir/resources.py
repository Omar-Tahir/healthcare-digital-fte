"""
FHIR resource parsing utilities.

Converts raw FHIR JSON responses into Pydantic domain models.
Handles Epic-specific deviations from the FHIR R4 spec documented
in DISC-003 and docs/skills/fhir-r4-integration.md.

Constitution: II.4 (no PHI in logs), II.5 (never raises to caller)
Spec: specs/05-fhir-integration.md
Skill: docs/skills/fhir-r4-integration.md
"""
from __future__ import annotations

import base64
import re
from datetime import datetime, timezone

import structlog

from src.core.models.encounter import (
    CodingClass,
    EncounterClass,
    OUTPATIENT_ENCOUNTER_CLASSES,
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

log = structlog.get_logger()


def get_encounter_coding_class(encounter: FHIREncounter) -> CodingClass:
    """
    Single authoritative mapping from encounter to coding rule class.

    OBS (observation status) returns OUTPATIENT — the most commonly
    confused mapping in hospital coding. Per ICD-10-CM Official
    Guidelines + CMS observation billing rules.
    """
    return get_coding_class(encounter.encounter_class)


def parse_patient(raw: dict) -> FHIRPatient:
    """
    Parse a FHIR Patient resource.

    Extracts only the system identifier (id).
    name, birthDate, address, and all other PHI fields are intentionally
    ignored — they are never needed by coding/CDI logic and must not
    reach memory, logs, or downstream models.
    """
    return FHIRPatient(id=raw["id"])


def parse_encounter(raw: dict) -> FHIREncounter:
    """
    Parse a FHIR Encounter resource.

    Maps Epic class codes to EncounterClass enum.
    Unknown class codes fall back to OUTPATIENT (conservative default
    per constitution Article II.6 — uncertain → conservative).
    """
    class_code = raw.get("class", {}).get("code", "AMB").upper()

    try:
        encounter_class = EncounterClass(class_code)
    except ValueError:
        log.warning(
            "unknown_encounter_class_code",
            class_code=class_code,
            fallback="AMB",
        )
        encounter_class = EncounterClass.OUTPATIENT

    period = raw.get("period", {})
    period_start = _parse_fhir_datetime(period.get("start", ""))
    period_end_str = period.get("end")
    period_end = _parse_fhir_datetime(period_end_str) if period_end_str else None

    attending_id: str | None = None
    for participant in raw.get("participant", []):
        ref = participant.get("individual", {}).get("reference", "")
        if ref.startswith("Practitioner/"):
            attending_id = ref.replace("Practitioner/", "")
            break

    return FHIREncounter(
        id=raw["id"],
        status=raw.get("status", "unknown"),
        class_code=class_code,
        encounter_class=encounter_class,
        period_start=period_start,
        period_end=period_end,
        attending_physician_id=attending_id,
    )


def parse_document_reference(raw: dict) -> FHIRDocumentReference | None:
    """
    Parse a FHIR DocumentReference resource into our domain model.

    Handles Epic's three content formats: plain text, CDA XML, and PDF.
    Returns None if essential fields are missing.
    Never raises — parse failures are logged without PHI.
    """
    try:
        doc_id = raw.get("id", "")
        if not doc_id:
            return None

        type_coding = raw.get("type", {}).get("coding", [{}])[0]
        note_type_loinc = type_coding.get("code", "")
        note_type_display = type_coding.get("display", "Clinical Note")

        authored_date = _parse_fhir_datetime(raw.get("date", ""))

        context = raw.get("context", {})
        encounter_refs = context.get("encounter", [])
        encounter_id = ""
        if encounter_refs:
            ref = encounter_refs[0].get("reference", "")
            encounter_id = ref.replace("Encounter/", "")

        content_list = raw.get("content", [])
        note_text: str | None = None
        binary_url: str | None = None
        content_type = NoteContentType.UNKNOWN

        if content_list:
            attachment = content_list[0].get("attachment", {})
            raw_ct = attachment.get("contentType", "")
            content_type = _map_content_type(raw_ct)
            extracted = extract_note_text(attachment)
            note_text = extracted if extracted else None
            # Epic returns note content via a Binary URL when no inline data
            if not note_text:
                url = attachment.get("url", "")
                if url:
                    binary_url = url

        return FHIRDocumentReference(
            id=doc_id,
            encounter_id=encounter_id,
            note_type_loinc=note_type_loinc,
            note_type_display=note_type_display,
            authored_date=authored_date,
            content_type=content_type,
            note_text=note_text,
            binary_url=binary_url,
        )

    except Exception as e:
        log.warning(
            "document_reference_parse_failed",
            error_type=type(e).__name__,
            # Never log raw document content — contains PHI
        )
        return None


def extract_note_text(attachment: dict) -> str:
    """
    Extract plain text from a FHIR content attachment.

    Handles:
    - text/plain  → base64 decode, return UTF-8 string directly
    - text/xml    → base64 decode, strip XML tags, return narrative
    - application/pdf → return "" (not supported without OCR)
    - unknown     → return ""

    Never raises.
    """
    if not attachment:
        return ""

    content_type = attachment.get("contentType", "")
    data_b64 = attachment.get("data", "")
    if not data_b64:
        return ""

    try:
        raw_bytes = base64.b64decode(data_b64)
    except Exception:
        return ""

    if "text/plain" in content_type:
        return _decode_utf8(raw_bytes)

    if "text/xml" in content_type or "application/xml" in content_type:
        return _extract_cda_narrative(raw_bytes)

    if "application/pdf" in content_type:
        log.warning(
            "pdf_note_not_extractable",
            content_type=content_type,
        )
        return ""

    return ""


def parse_observation(raw: dict) -> FHIRObservation | None:
    """
    Parse a FHIR Observation resource (lab value or vital sign).

    Returns None on any parse failure — caller ignores missing observations.
    Never raises.
    """
    try:
        loinc_code = ""
        display = ""
        for coding in raw.get("code", {}).get("coding", []):
            if "loinc.org" in coding.get("system", ""):
                loinc_code = coding.get("code", "")
                display = coding.get("display", "")
                break

        value_qty = raw.get("valueQuantity", {})
        value_quantity: float | None = value_qty.get("value") if value_qty else None
        value_string: str | None = raw.get("valueString")
        unit: str | None = value_qty.get("unit") if value_qty else None

        interp_list = raw.get("interpretation", [])
        interpretation: str | None = None
        if interp_list:
            interpretation = (
                interp_list[0].get("coding", [{}])[0].get("code")
            )

        effective = raw.get("effectiveDateTime", "")

        return FHIRObservation(
            id=raw.get("id", ""),
            loinc_code=loinc_code,
            display=display,
            value_quantity=value_quantity,
            value_string=value_string,
            unit=unit,
            effective_datetime=_parse_fhir_datetime(effective),
            interpretation=interpretation,
        )

    except Exception as e:
        log.warning(
            "observation_parse_failed",
            error_type=type(e).__name__,
        )
        return None


# ─── Private helpers ──────────────────────────────────────────────────────────


def _extract_cda_narrative(xml_bytes: bytes) -> str:
    """Strip XML markup from CDA R2 content, returning readable narrative."""
    try:
        xml_str = xml_bytes.decode("utf-8", errors="replace")
        text = re.sub(r"<[^>]+>", " ", xml_str)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        return ""


def _decode_utf8(raw_bytes: bytes) -> str:
    """Decode bytes to UTF-8 string, replacing undecodable characters."""
    try:
        return raw_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _map_content_type(raw: str) -> NoteContentType:
    """Map a MIME type string to NoteContentType enum."""
    if "text/plain" in raw:
        return NoteContentType.PLAIN_TEXT
    if "text/xml" in raw or "application/xml" in raw:
        return NoteContentType.CDA_XML
    if "application/pdf" in raw:
        return NoteContentType.PDF_BASE64
    return NoteContentType.UNKNOWN


def _parse_fhir_datetime(dt_str: str) -> datetime:
    """
    Parse a FHIR datetime string to a timezone-aware datetime.
    Returns utcnow() on any parse failure so callers always get a valid datetime.
    """
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        normalized = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)
