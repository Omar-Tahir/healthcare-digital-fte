"""
Integration tests for EpicCodingPipeline against Epic sandbox.

Requires: FHIR_BASE_URL, FHIR_CLIENT_ID, FHIR_PRIVATE_KEY_PATH in .env
Network access to fhir.epic.com

Run:
  python -m pytest tests/integration/test_epic_coding_pipeline.py -v -s

PHI policy: Epic sandbox uses synthetic patients only (Article II.4).
Spec: specs/09-epic-coding-pipeline.md
"""
from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from src.core.fhir.client import FHIRClient
from src.core.fhir.pipeline import EpicCodingPipeline, PipelineResult
from src.core.models.fhir import DegradedResult

EPIC_TEST_PATIENT = "eq081-VQEgP8drUUqCWzHfw3"  # Derrick Lin — Backend Services patient


@pytest.fixture(scope="module")
def fhir_client() -> FHIRClient:
    base_url = os.getenv("FHIR_BASE_URL", "")
    client_id = os.getenv("FHIR_CLIENT_ID", "")
    key_path = os.getenv("FHIR_PRIVATE_KEY_PATH", "")

    if not all([base_url, client_id, key_path]) or "path/to" in key_path:
        pytest.skip("FHIR env vars not configured")
    if not os.path.exists(key_path):
        pytest.skip(f"Private key not found at {key_path}")

    return FHIRClient(
        base_url=base_url,
        client_id=client_id,
        private_key_pem=open(key_path).read(),
        kid=os.getenv("FHIR_KID"),
    )


@pytest.fixture(scope="module")
def pipeline(fhir_client: FHIRClient) -> EpicCodingPipeline:
    return EpicCodingPipeline(fhir_client=fhir_client)


@pytest.fixture(scope="module")
async def real_encounter_id(fhir_client: FHIRClient) -> str:
    """Fetch a real encounter ID from Epic sandbox for the test patient."""
    raw = await fhir_client._get(
        "/Encounter",
        params={"patient": EPIC_TEST_PATIENT, "_count": "1"},
    )
    if isinstance(raw, DegradedResult) or not raw.get("entry"):
        pytest.skip("No encounters found for test patient")
    return raw["entry"][0]["resource"]["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_run_returns_result(
    pipeline: EpicCodingPipeline,
    real_encounter_id: str,
) -> None:
    """Full pipeline run returns a PipelineResult (not DegradedResult)."""
    result = await pipeline.run(
        patient_id=EPIC_TEST_PATIENT,
        encounter_id=real_encounter_id,
    )
    assert isinstance(result, PipelineResult), (
        f"Expected PipelineResult, got {type(result).__name__}"
    )
    assert result.patient_id == EPIC_TEST_PATIENT
    assert result.encounter_id == real_encounter_id
    assert result.processing_time_ms > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_notes_analyzed(
    pipeline: EpicCodingPipeline,
    real_encounter_id: str,
) -> None:
    """Pipeline reports how many notes were analyzed."""
    result = await pipeline.run(
        patient_id=EPIC_TEST_PATIENT,
        encounter_id=real_encounter_id,
    )
    assert isinstance(result, PipelineResult)
    # notes_analyzed >= 0; 0 is valid for sandbox patients with no notes
    assert result.notes_analyzed >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_suggestions_have_evidence(
    pipeline: EpicCodingPipeline,
    real_encounter_id: str,
) -> None:
    """All returned suggestions include an evidence_quote (Article II.2)."""
    result = await pipeline.run(
        patient_id=EPIC_TEST_PATIENT,
        encounter_id=real_encounter_id,
    )
    if not isinstance(result, PipelineResult):
        pytest.skip("Pipeline returned non-PipelineResult")
    for s in result.suggestions:
        assert s.evidence_quote, f"Suggestion {s.code} missing evidence_quote"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_degraded_on_invalid_encounter(
    pipeline: EpicCodingPipeline,
) -> None:
    """Invalid encounter ID returns degraded PipelineResult (Article II.5)."""
    result = await pipeline.run(
        patient_id=EPIC_TEST_PATIENT,
        encounter_id="invalid-encounter-that-does-not-exist",
    )
    assert isinstance(result, PipelineResult)
    assert result.is_degraded is True
    assert result.suggestions == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_draft_claim_written(
    pipeline: EpicCodingPipeline,
    real_encounter_id: str,
) -> None:
    """When suggestions exist, pipeline attempts to write a draft Claim to Epic."""
    result = await pipeline.run(
        patient_id=EPIC_TEST_PATIENT,
        encounter_id=real_encounter_id,
    )
    assert isinstance(result, PipelineResult)
    # draft_claim_id may be None if Epic sandbox rejects Claim POST
    # or if no suggestions were produced — both are valid degraded states
    if result.suggestions:
        # If we have suggestions, we attempted a claim write
        # (sandbox may or may not return an ID — either is acceptable)
        assert result.draft_claim_id is not None or result.is_degraded


@pytest.mark.unit
def test_merge_deduplication() -> None:
    """Same ICD-10 code from two notes → highest-confidence instance kept."""
    from src.core.fhir.pipeline import _merge_suggestions
    from src.core.models.coding import CodingSuggestion

    low = CodingSuggestion(
        code="I50.21",
        description="Systolic HF, acute",
        confidence=0.70,
        evidence_quote="heart failure",
        drg_impact="",
        drg_revenue_delta=500.0,
    )
    high = CodingSuggestion(
        code="I50.21",
        description="Systolic HF, acute",
        confidence=0.92,
        evidence_quote="acute systolic heart failure",
        drg_impact="",
        drg_revenue_delta=500.0,
    )
    different = CodingSuggestion(
        code="E11.22",
        description="T2DM with CKD",
        confidence=0.85,
        evidence_quote="type 2 diabetes",
        drg_impact="",
        drg_revenue_delta=300.0,
    )

    merged = _merge_suggestions([[low, different], [high]])
    codes = [s.code for s in merged]

    assert codes.count("I50.21") == 1, "Duplicate code must be deduped"
    i50 = next(s for s in merged if s.code == "I50.21")
    assert i50.confidence == 0.92, "Higher-confidence instance must be kept"
    assert "E11.22" in codes
