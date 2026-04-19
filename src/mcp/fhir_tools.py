"""
MCP tools — FHIR resource lookups.

Thin async wrappers over FHIRClient. Agents call these instead of
injecting full patient records into context (Skills + MCP pattern).

All tools return structured dicts or DegradedResult dicts.
None of these tools log PHI — constitution Article II.4.

Constitution: II.1 (draft claims only), II.4 (no PHI in logs),
              II.5 (graceful degradation — never raises)
Skill: docs/skills/fhir-r4-integration.md
"""
from __future__ import annotations

import os

from src.core.fhir.client import FHIRClient
from src.core.models.fhir import DegradedResult

_FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "")
_FHIR_CLIENT_ID = os.getenv("FHIR_CLIENT_ID", "")
_FHIR_PRIVATE_KEY_PEM = os.getenv("FHIR_PRIVATE_KEY_PEM", "")
_FHIR_TOKEN_URL = os.getenv("FHIR_TOKEN_URL", "")


def _get_client() -> FHIRClient:
    return FHIRClient(
        base_url=_FHIR_BASE_URL,
        client_id=_FHIR_CLIENT_ID,
        private_key_pem=_FHIR_PRIVATE_KEY_PEM,
        token_url=_FHIR_TOKEN_URL,
    )


async def mcp_fhir_get_encounter(encounter_id: str) -> dict[str, object]:
    """
    Fetch encounter resource by ID.

    Returns encounter dict or {"error_code": ..., "error_message": ...}.
    """
    client = _get_client()
    result = await client.get_encounter(encounter_id)
    if isinstance(result, DegradedResult):
        return {"error_code": result.error_code, "error_message": result.error_message}
    return {
        "id": result.id,
        "status": result.status,
        "class_code": result.class_code,
        "encounter_class": result.encounter_class.value,
    }


async def mcp_fhir_get_clinical_notes(
    patient_id: str,
    encounter_id: str,
) -> dict[str, object]:
    """
    Fetch clinical notes for a patient encounter.

    Returns {"notes": [{"id": ..., "note_type": ..., "has_text": bool}]}
    or {"error_code": ..., "error_message": ...}.
    Never returns note text — agents fetch note content via the coding pipeline.
    """
    client = _get_client()
    try:
        notes = await client.get_clinical_notes(patient_id, encounter_id)
        return {
            "notes": [
                {
                    "id": n.id,
                    "note_type": n.note_type_display,
                    "authored_date": n.authored_date.isoformat() if n.authored_date else None,
                    "has_text": bool(n.note_text),
                }
                for n in notes
            ]
        }
    except Exception as e:
        return {"error_code": "FHIR_NOTES_FAILED", "error_message": type(e).__name__}


async def mcp_fhir_get_recent_labs(
    patient_id: str,
    encounter_id: str,
    loinc_codes: list[str],
) -> dict[str, object]:
    """
    Fetch recent lab observations filtered by LOINC codes.

    Returns {"observations": [{"id": ..., "loinc_code": ..., "value": ..., "unit": ...}]}
    or {"error_code": ..., "error_message": ...}.
    """
    client = _get_client()
    try:
        observations = await client.get_recent_labs(patient_id, encounter_id, loinc_codes)
        return {
            "observations": [
                {
                    "id": o.id,
                    "loinc_code": o.loinc_code,
                    "value_quantity": o.value_quantity,
                    "unit": o.unit,
                    "effective_datetime": o.effective_datetime.isoformat() if o.effective_datetime else None,
                }
                for o in observations
            ]
        }
    except Exception as e:
        return {"error_code": "FHIR_LABS_FAILED", "error_message": type(e).__name__}
