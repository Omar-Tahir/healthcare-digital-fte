"""
Integration tests for FHIRClient against Epic sandbox.

These tests hit real Epic endpoints using the sandbox test patients.
They require:
  - FHIR_BASE_URL, FHIR_CLIENT_ID, FHIR_PRIVATE_KEY_PATH in .env
  - Public key uploaded to Epic developer portal
  - Network access to fhir.epic.com

Run with:
  uv run pytest tests/integration/test_fhir_client.py -m integration -v

PHI policy: Epic sandbox uses synthetic patients only (constitution Article II.4).
No real PHI is involved. However, we still log only IDs — never resource content.

Spec: specs/05-fhir-integration.md
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv

load_dotenv()

from src.core.fhir.client import FHIRClient
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
    FHIRPatient,
)

# Epic sandbox test patients — synthetic data only, no real PHI.
# Source: https://fhir.epic.com/Documentation?docId=testpatients
EPIC_TEST_PATIENT_ADULT = "eJzlzPIHTYPFGhMqw.P9XA3"
EPIC_TEST_PATIENT_PEDIATRIC = "erXuFYUfucBZaryVksYEcMg3"


@pytest.fixture(scope="module")
def fhir_client() -> FHIRClient:
    """Build FHIRClient from env vars. Skips if env not configured."""
    base_url = os.getenv("FHIR_BASE_URL", "")
    client_id = os.getenv("FHIR_CLIENT_ID", "")
    key_path = os.getenv("FHIR_PRIVATE_KEY_PATH", "")

    if not all([base_url, client_id, key_path]) or "path/to" in key_path:
        pytest.skip("FHIR env vars not configured — set FHIR_BASE_URL, FHIR_CLIENT_ID, FHIR_PRIVATE_KEY_PATH")

    if not os.path.exists(key_path):
        pytest.skip(f"Private key not found at {key_path} — run: openssl genrsa -out {key_path} 2048")

    return FHIRClient(
        base_url=base_url,
        client_id=client_id,
        private_key_pem=open(key_path).read(),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_authentication(fhir_client: FHIRClient) -> None:
    """Auth token is obtained successfully from Epic token endpoint."""
    token = await fhir_client._auth.get_token()
    assert token is not None, (
        "Authentication failed. Check: Client ID in .env, public key in Epic portal, key pair match."
    )
    assert len(token) > 20


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_patient(fhir_client: FHIRClient) -> None:
    """Patient resource is fetched for Epic sandbox adult test patient."""
    result = await fhir_client.get_patient(EPIC_TEST_PATIENT_ADULT)
    assert not isinstance(result, DegradedResult), (
        f"Patient fetch degraded: {result.error_code if isinstance(result, DegradedResult) else 'unknown'}"
    )
    assert isinstance(result, FHIRPatient)
    assert result.id == EPIC_TEST_PATIENT_ADULT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_encounter_search(fhir_client: FHIRClient) -> None:
    """Encounter search returns at least one encounter for the adult test patient."""
    raw = await fhir_client._get(
        "/Encounter",
        params={"patient": EPIC_TEST_PATIENT_ADULT, "_count": "5"},
    )
    assert not isinstance(raw, DegradedResult), (
        f"Encounter search degraded: {raw.error_code if isinstance(raw, DegradedResult) else 'unknown'}"
    )
    entries = raw.get("entry", [])
    assert len(entries) >= 1, "Expected at least one encounter for test patient"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_encounter_by_id(fhir_client: FHIRClient) -> None:
    """Encounter by ID returns a parsed FHIREncounter with encounter_class set."""
    # First search to get a real encounter ID
    raw = await fhir_client._get(
        "/Encounter",
        params={"patient": EPIC_TEST_PATIENT_ADULT, "_count": "1"},
    )
    if isinstance(raw, DegradedResult) or not raw.get("entry"):
        pytest.skip("No encounters found for test patient")

    encounter_id = raw["entry"][0]["resource"]["id"]
    result = await fhir_client.get_encounter(encounter_id)

    assert not isinstance(result, DegradedResult), (
        f"Encounter fetch degraded: {result.error_code if isinstance(result, DegradedResult) else 'unknown'}"
    )
    assert isinstance(result, FHIREncounter)
    assert result.id == encounter_id
    assert result.encounter_class is not None, "encounter_class must be set — needed for coding rule selection"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_clinical_notes(fhir_client: FHIRClient) -> None:
    """Clinical notes fetch returns a list (may be empty for test patient)."""
    notes = await fhir_client.get_clinical_notes(
        patient_id=EPIC_TEST_PATIENT_ADULT,
        encounter_id="",
    )
    # Empty list is valid — test patient may have no notes in sandbox
    assert isinstance(notes, list)
    for note in notes:
        assert isinstance(note, FHIRDocumentReference)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_caching(fhir_client: FHIRClient) -> None:
    """Second get_token() call returns cached token without a new HTTP round-trip."""
    token1 = await fhir_client._auth.get_token()
    token2 = await fhir_client._auth.get_token()
    assert token1 == token2, "Token cache is not working — two requests obtained different tokens"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_degraded_on_invalid_patient(fhir_client: FHIRClient) -> None:
    """Invalid patient ID returns DegradedResult, not an exception (Article II.5)."""
    result = await fhir_client.get_patient("invalid-patient-id-that-does-not-exist")
    assert isinstance(result, DegradedResult), (
        "Expected DegradedResult for invalid patient ID — never raise to caller"
    )
