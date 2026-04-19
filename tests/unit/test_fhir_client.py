"""
FHIR R4 client unit tests — BUILD-005.

TDD red → green following constitution Article I.2.
All HTTP calls are mocked — no real Epic connection required.

Constitution: II.1 (draft claim), II.4 (no PHI in logs), II.5 (degradation)
Spec: specs/05-fhir-integration.md
Skill: docs/skills/fhir-r4-integration.md
"""
from __future__ import annotations

import base64
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.fhir.client import FHIRClient
from src.core.fhir.resources import (
    extract_note_text,
    get_encounter_coding_class,
    parse_document_reference,
    parse_encounter,
    parse_observation,
    parse_patient,
)
from src.core.models.encounter import CodingClass, EncounterClass
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
    FHIRObservation,
    FHIRPatient,
    NoteContentType,
)

# ─── Mock FHIR API Responses ─────────────────────────────────────────────────
# PHI present intentionally — tests verify it never reaches logs.

MOCK_PATIENT_RESPONSE = {
    "resourceType": "Patient",
    "id": "patient-123",
    "name": [{"family": "Smith", "given": ["John"]}],
    "birthDate": "1945-03-15",
    "gender": "male",
}

MOCK_ENCOUNTER_IMP = {
    "resourceType": "Encounter",
    "id": "encounter-456",
    "status": "in-progress",
    "class": {"code": "IMP", "display": "inpatient encounter"},
    "period": {"start": "2026-04-01T08:00:00Z"},
    "participant": [{"individual": {"reference": "Practitioner/prac-789"}}],
}

MOCK_ENCOUNTER_OBS = {
    "resourceType": "Encounter",
    "id": "encounter-obs",
    "status": "in-progress",
    "class": {"code": "OBS", "display": "observation encounter"},
    "period": {"start": "2026-04-01T08:00:00Z"},
}

_PLAIN_TEXT_NOTE = "Patient presents with chest pain and shortness of breath."
MOCK_DOCUMENT_REFERENCE = {
    "resourceType": "DocumentReference",
    "id": "doc-001",
    "status": "current",
    "type": {
        "coding": [
            {
                "system": "http://loinc.org",
                "code": "34117-2",
                "display": "H&P Note",
            }
        ]
    },
    "context": {"encounter": [{"reference": "Encounter/encounter-456"}]},
    "date": "2026-04-01T10:00:00Z",
    "content": [
        {
            "attachment": {
                "contentType": "text/plain",
                "data": base64.b64encode(_PLAIN_TEXT_NOTE.encode()).decode(),
            }
        }
    ],
}

MOCK_OBSERVATION_BUNDLE = {
    "resourceType": "Bundle",
    "entry": [
        {
            "resource": {
                "resourceType": "Observation",
                "id": "obs-creatinine-001",
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "2160-0",
                            "display": "Creatinine [Mass/volume] in Serum",
                        }
                    ]
                },
                "valueQuantity": {"value": 2.4, "unit": "mg/dL"},
                "effectiveDateTime": "2026-04-01T09:00:00Z",
                "interpretation": [{"coding": [{"code": "H"}]}],
            }
        }
    ],
}

MOCK_NOTES_BUNDLE = {
    "resourceType": "Bundle",
    "entry": [{"resource": MOCK_DOCUMENT_REFERENCE}],
}


# ─── GROUP A: Encounter Class Mapping ─────────────────────────────────────────

class TestEncounterClassMapping:
    """
    Verifies the most critical mapping in healthcare AI.
    OBS (observation) must use OUTPATIENT coding rules.
    Getting this wrong causes False Claims Act exposure.
    Skill: docs/skills/fhir-r4-integration.md Section 3
    """

    def _make_encounter(self, class_code: str) -> FHIREncounter:
        from datetime import datetime, timezone
        return FHIREncounter(
            id="enc-test",
            status="in-progress",
            class_code=class_code,
            encounter_class=EncounterClass(class_code),
            period_start=datetime.now(timezone.utc),
        )

    def test_inpatient_maps_to_inpatient_coding_class(self) -> None:
        """IMP → CodingClass.INPATIENT"""
        enc = self._make_encounter("IMP")
        assert get_encounter_coding_class(enc) == CodingClass.INPATIENT

    def test_outpatient_maps_to_outpatient_coding_class(self) -> None:
        """AMB → CodingClass.OUTPATIENT"""
        enc = self._make_encounter("AMB")
        assert get_encounter_coding_class(enc) == CodingClass.OUTPATIENT

    def test_observation_status_maps_to_outpatient_coding_class(self) -> None:
        """
        OBS → CodingClass.OUTPATIENT
        CRITICAL: Observation-status patients use outpatient coding rules.
        Per ICD-10-CM Official Guidelines + CMS OBS status billing rules.
        This is the most commonly confused mapping in hospital coding AI.
        """
        enc = self._make_encounter("OBS")
        assert get_encounter_coding_class(enc) == CodingClass.OUTPATIENT

    def test_emergency_maps_to_outpatient_coding_class(self) -> None:
        """EMER → CodingClass.OUTPATIENT"""
        enc = self._make_encounter("EMER")
        assert get_encounter_coding_class(enc) == CodingClass.OUTPATIENT


# ─── GROUP B: Note Text Extraction ────────────────────────────────────────────

class TestNoteTextExtraction:
    """
    Epic sends notes in multiple formats.
    extract_note_text() must handle all without raising.
    """

    def test_plain_text_extracted_from_base64(self) -> None:
        """text/plain + base64 → decoded UTF-8 string."""
        attachment = {
            "contentType": "text/plain",
            "data": base64.b64encode(
                b"Patient presents with heart failure."
            ).decode(),
        }
        result = extract_note_text(attachment)
        assert result == "Patient presents with heart failure."

    def test_cda_xml_narrative_extracted(self) -> None:
        """
        text/xml CDA → strip XML markup, return readable text.
        Verifies XML tags are removed and narrative preserved.
        """
        cda_text = "<section><text>Chest pain on exertion.</text></section>"
        attachment = {
            "contentType": "text/xml",
            "data": base64.b64encode(cda_text.encode()).decode(),
        }
        result = extract_note_text(attachment)
        assert "Chest pain on exertion" in result
        assert "<text>" not in result
        assert "<section>" not in result

    def test_pdf_returns_empty_string(self) -> None:
        """application/pdf → "" — not supported. Never raise."""
        attachment = {
            "contentType": "application/pdf",
            "data": base64.b64encode(b"%PDF-1.4 fake pdf").decode(),
        }
        result = extract_note_text(attachment)
        assert result == ""

    def test_unknown_content_type_returns_empty_string(self) -> None:
        """Unknown contentType → "" — never raise."""
        attachment = {
            "contentType": "application/octet-stream",
            "data": base64.b64encode(b"binary data").decode(),
        }
        result = extract_note_text(attachment)
        assert result == ""


# ─── GROUP C: FHIR Client (mocked HTTP) ───────────────────────────────────────

class TestFHIRClientMocked:
    """
    All FHIR HTTP calls are mocked with patch.object.
    Tests cover the full request/parse/degrade cycle.
    """

    @pytest.fixture
    def client(self) -> FHIRClient:
        return FHIRClient(
            base_url="https://fhir.epic.com/test/api/FHIR/R4",
            client_id="test-client-id",
            private_key_pem="fake-key",
        )

    @pytest.mark.asyncio
    async def test_get_patient_returns_fhir_patient(
        self, client: FHIRClient
    ) -> None:
        """Successful FHIR response → FHIRPatient with correct id."""
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            return_value=MagicMock(
                status_code=200,
                json=lambda: MOCK_PATIENT_RESPONSE,
                raise_for_status=lambda: None,
            ),
        ):
            result = await client.get_patient("patient-123")

        assert isinstance(result, FHIRPatient)
        assert result.id == "patient-123"

    @pytest.mark.asyncio
    async def test_get_patient_returns_degraded_on_connect_error(
        self, client: FHIRClient
    ) -> None:
        """
        httpx.ConnectError → DegradedResult(is_degraded=True).
        Article II.5: caller never receives an exception.
        """
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await client.get_patient("patient-123")

        assert isinstance(result, DegradedResult)
        assert result.is_degraded is True
        assert result.error_code == "FHIR_GET_PATIENT_FAILED"

    @pytest.mark.asyncio
    async def test_get_patient_returns_degraded_on_404(
        self, client: FHIRClient
    ) -> None:
        """HTTP 404 → DegradedResult, not KeyError or exception."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.get_patient("patient-999")

        assert isinstance(result, DegradedResult)
        assert result.is_degraded is True

    @pytest.mark.asyncio
    async def test_get_encounter_infers_encounter_class(
        self, client: FHIRClient
    ) -> None:
        """Encounter with class.code='IMP' → EncounterClass.INPATIENT."""
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            return_value=MagicMock(
                status_code=200,
                json=lambda: MOCK_ENCOUNTER_IMP,
                raise_for_status=lambda: None,
            ),
        ):
            result = await client.get_encounter("encounter-456")

        assert isinstance(result, FHIREncounter)
        assert result.encounter_class == EncounterClass.INPATIENT

    @pytest.mark.asyncio
    async def test_get_encounter_obs_sets_observation_class(
        self, client: FHIRClient
    ) -> None:
        """Encounter with class.code='OBS' → EncounterClass.OBSERVATION."""
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            return_value=MagicMock(
                status_code=200,
                json=lambda: MOCK_ENCOUNTER_OBS,
                raise_for_status=lambda: None,
            ),
        ):
            result = await client.get_encounter("encounter-obs")

        assert isinstance(result, FHIREncounter)
        assert result.encounter_class == EncounterClass.OBSERVATION

    @pytest.mark.asyncio
    async def test_get_clinical_notes_returns_document_references(
        self, client: FHIRClient
    ) -> None:
        """Bundle with one entry → list[FHIRDocumentReference] of length 1."""
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            return_value=MagicMock(
                status_code=200,
                json=lambda: MOCK_NOTES_BUNDLE,
                raise_for_status=lambda: None,
            ),
        ):
            result = await client.get_clinical_notes("patient-123", "encounter-456")

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], FHIRDocumentReference)
        assert _PLAIN_TEXT_NOTE in (result[0].note_text or "")

    @pytest.mark.asyncio
    async def test_get_clinical_notes_returns_empty_list_on_error(
        self, client: FHIRClient
    ) -> None:
        """
        httpx.TimeoutException → [] (empty list).
        Article II.5: workflow continues without notes.
        """
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            result = await client.get_clinical_notes("patient-123", "encounter-456")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_recent_labs_returns_observations(
        self, client: FHIRClient
    ) -> None:
        """Bundle with creatinine observation → list[FHIRObservation]."""
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            return_value=MagicMock(
                status_code=200,
                json=lambda: MOCK_OBSERVATION_BUNDLE,
                raise_for_status=lambda: None,
            ),
        ):
            result = await client.get_recent_labs(
                "patient-123", "encounter-456", ["2160-0"]
            )

        assert isinstance(result, list)
        assert len(result) == 1
        obs = result[0]
        assert isinstance(obs, FHIRObservation)
        assert obs.loinc_code == "2160-0"
        assert obs.value_quantity == 2.4
        assert obs.interpretation == "H"


# ─── GROUP D: Draft Claim Write + PHI Safety ──────────────────────────────────

class TestFHIRClaimWrite:
    """
    Constitution Article II.1: claim status must always be "draft".
    The FHIR write layer enforces this — callers cannot override it.
    """

    @pytest.fixture
    def client(self) -> FHIRClient:
        return FHIRClient(
            base_url="https://fhir.epic.com/test/api/FHIR/R4",
            client_id="test-client-id",
            private_key_pem="fake-key",
        )

    @pytest.mark.asyncio
    async def test_write_draft_claim_status_is_always_draft(
        self, client: FHIRClient
    ) -> None:
        """
        Article II.1 enforcement: POST payload must contain status="draft".
        Captures the actual payload sent over the wire via mock_post.
        """
        captured_payload: dict = {}

        async def mock_post(url: str, json: dict | None = None, **kwargs: object) -> MagicMock:
            captured_payload.update(json or {})
            return MagicMock(
                status_code=201,
                json=lambda: {"resourceType": "Claim", "id": "claim-001"},
                raise_for_status=lambda: None,
            )

        with patch.object(client._http, "post", new_callable=AsyncMock, side_effect=mock_post):
            mock_result = MagicMock()
            mock_result.suggestions = []
            mock_result.encounter_id = "encounter-789"

            await client.write_draft_claim(
                encounter_id="encounter-789",
                coding_result=mock_result,
            )

        assert captured_payload.get("status") == "draft"
        assert captured_payload.get("status") != "active"

    @pytest.mark.asyncio
    async def test_write_draft_claim_returns_degraded_on_error(
        self, client: FHIRClient
    ) -> None:
        """httpx.ConnectError during POST → DegradedResult, workflow continues."""
        with patch.object(
            client._http, "post", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("FHIR unavailable"),
        ):
            mock_result = MagicMock()
            mock_result.suggestions = []
            mock_result.encounter_id = "encounter-789"

            result = await client.write_draft_claim(
                encounter_id="encounter-789",
                coding_result=mock_result,
            )

        assert isinstance(result, DegradedResult)
        assert result.is_degraded is True


class TestFHIRClientPHISafety:
    """
    Constitution Article II.4: PHI must never appear in any log.
    FHIR responses contain real patient data — the client strips it
    before any structlog call.
    """

    @pytest.fixture
    def client(self) -> FHIRClient:
        return FHIRClient(
            base_url="https://fhir.epic.com/test/api/FHIR/R4",
            client_id="test-client-id",
            private_key_pem="fake-key",
        )

    @pytest.mark.asyncio
    async def test_patient_name_never_in_logs(
        self, client: FHIRClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        MOCK_PATIENT_RESPONSE contains "Smith" and "John".
        After get_patient(), neither must appear in any log record.
        """
        with caplog.at_level(logging.DEBUG):
            with patch.object(
                client._http, "get", new_callable=AsyncMock,
                return_value=MagicMock(
                    status_code=200,
                    json=lambda: MOCK_PATIENT_RESPONSE,
                    raise_for_status=lambda: None,
                ),
            ):
                await client.get_patient("patient-123")

        assert "Smith" not in caplog.text
        assert "John" not in caplog.text
        assert "1945" not in caplog.text  # birth year from birthDate

    @pytest.mark.asyncio
    async def test_error_message_contains_no_phi(
        self, client: FHIRClient
    ) -> None:
        """
        DegradedResult.error_message must describe only the error type.
        Must not contain patient identifiers or clinical content.
        """
        with patch.object(
            client._http, "get", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused to patient-123"),
        ):
            result = await client.get_patient("patient-123")

        assert isinstance(result, DegradedResult)
        # error_message is a system description only
        assert "patient-123" not in result.error_message
        assert len(result.error_message) > 0  # not empty — must describe error
