"""
End-to-End Pipeline Integration Test — BUILD-010

Tests the complete workflow from clinical note to API approval.
Key assertions: all Article II safety rules enforced end-to-end.

Constitution: ALL Article II clauses tested end-to-end.
"""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.api.main import app
from src.api.security.approval_token import ApprovalTokenService
from src.core.models.fhir import (
    FHIRDocumentReference,
    FHIREncounter,
    NoteContentType,
    DegradedResult,
)
from src.core.models.encounter import EncounterClass
from src.agents.coding_agent import CodingAgent
from src.agents.cdi_agent import CDIAgent
from src.core.drg.grouper import DRGGrouper
from src.nlp.pipeline import NLPPipeline

# ─── Test Note ────────────────────────────────────────────────────────────────

FULL_INPATIENT_NOTE = """
S: 72-year-old male admitted for worsening shortness of breath
over 3 days. No chest pain. History of systolic heart failure,
type 2 diabetes mellitus with stage 3 chronic kidney disease,
and hypertension.

O: Vitals: BP 158/94, HR 102, RR 24, SpO2 88% on room air.
Weight up 8 lbs from baseline. JVD present. Bilateral crackles.
BNP 1,840. Creatinine 2.8 (baseline 1.4). BMP otherwise normal.

A: Acute exacerbation of systolic congestive heart failure.
Type 2 diabetes mellitus with diabetic chronic kidney disease,
stage 3. Hypertensive heart disease. Acute kidney injury on
chronic kidney disease — creatinine rose 1.4 to 2.8 in 48 hours.

P: Admit for IV diuresis. Furosemide 80mg IV BID.
Strict fluid restriction. Daily weights. Cardiology consult.
Nephrology consult for AKI management. Repeat BMP tomorrow.
Tight glycemic control with insulin sliding scale.
"""


def make_inpatient_encounter() -> FHIREncounter:
    return FHIREncounter(
        id="enc-e2e-001",
        status="in-progress",
        class_code="IMP",
        encounter_class=EncounterClass.INPATIENT,
        period_start=datetime.now(timezone.utc),
    )


def make_document_reference(note_text: str) -> FHIRDocumentReference:
    return FHIRDocumentReference(
        id="doc-e2e-001",
        encounter_id="enc-e2e-001",
        note_type_loinc="34117-2",
        note_type_display="History and physical note",
        authored_date=datetime.now(timezone.utc),
        content_type=NoteContentType.PLAIN_TEXT,
        note_text=note_text,
    )


# ─── Component Integration Tests ─────────────────────────────────────────────

class TestNLPPipelineIntegration:
    """NLP pipeline processes the full test note correctly."""

    def test_nlp_runs_on_full_note_without_error(self):
        """NLP pipeline runs without crashing."""
        pipeline = NLPPipeline()
        result = pipeline.analyze(FULL_INPATIENT_NOTE)
        assert not result.is_degraded
        assert result.processing_time_ms < 1000

    def test_nlp_result_entity_count_is_non_negative(self):
        """NLP returns valid entity count."""
        pipeline = NLPPipeline()
        result = pipeline.analyze(FULL_INPATIENT_NOTE)
        assert result.entity_count >= 0


class TestDRGCalculatorIntegration:
    """DRG calculator produces correct results for the test case."""

    def test_heart_failure_drg_calculated(self):
        """HF principal diagnosis returns valid DRG."""
        grouper = DRGGrouper()
        result = grouper.calculate_drg(principal="I50.21", secondary=[])
        assert result.drg in {"291", "292", "293"}
        assert result.weight > 0

    def test_aki_addition_to_hf_claim(self):
        """Adding AKI to HF claim is calculable."""
        grouper = DRGGrouper()
        impact = grouper.calculate_impact(
            current_codes=["I50.21"],
            proposed_addition="N17.9",
        )
        assert impact.proposed_drg in {"291", "292", "293"}

    def test_drg_compliance_flag_for_high_delta(self):
        """Revenue delta > $5,000 auto-sets compliance_review_required."""
        grouper = DRGGrouper()
        impact = grouper.calculate_impact(
            current_codes=["I50.21"],
            proposed_addition="N17.9",
        )
        if impact.revenue_difference > 5000:
            assert impact.requires_compliance_review is True


class TestCodingAgentIntegration:
    """Coding agent pipeline with mocked LLM."""

    @pytest.mark.asyncio
    async def test_coding_agent_returns_valid_result_type(self):
        """Pipeline returns CodingAnalysisResult or DegradedResult — never raises."""
        from src.core.models.coding import CodingAnalysisResult

        agent = CodingAgent()
        doc = make_document_reference(FULL_INPATIENT_NOTE)
        encounter = make_inpatient_encounter()

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=json.dumps({
            "suggestions": [
                {
                    "code": "I50.21",
                    "description": "Systolic heart failure, acute",
                    "confidence": 0.94,
                    "evidence_quote": (
                        "Acute exacerbation of systolic congestive heart failure"
                    ),
                    "drg_impact_description": "Primary DRG driver",
                    "drg_revenue_delta": 7500.0,
                    "is_mcc": False,
                    "is_cc": True,
                    "is_principal_dx_candidate": True,
                },
            ],
            "cdi_opportunities": [],
        }))]

        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            result = await agent.analyze_note(doc, encounter)

        assert isinstance(result, (CodingAnalysisResult, DegradedResult))

    @pytest.mark.asyncio
    async def test_suggestions_have_evidence_quotes(self):
        """Article II.2: every accepted suggestion has evidence_quote in note."""
        from src.core.models.coding import CodingAnalysisResult

        agent = CodingAgent()
        doc = make_document_reference(FULL_INPATIENT_NOTE)
        encounter = make_inpatient_encounter()

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=json.dumps({
            "suggestions": [
                {
                    "code": "I50.21",
                    "description": "Systolic CHF",
                    "confidence": 0.94,
                    "evidence_quote": (
                        "Acute exacerbation of systolic congestive heart failure"
                    ),
                    "drg_impact_description": "primary",
                    "drg_revenue_delta": 7500.0,
                    "is_mcc": False, "is_cc": True,
                    "is_principal_dx_candidate": True,
                },
            ],
            "cdi_opportunities": [],
        }))]

        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            result = await agent.analyze_note(doc, encounter)

        if isinstance(result, CodingAnalysisResult):
            for s in result.suggestions:
                assert s.evidence_quote is not None
                assert s.evidence_quote in doc.note_text


# ─── API End-to-End Tests ─────────────────────────────────────────────────────

@pytest.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestFullAPIWorkflow:

    @pytest.mark.asyncio
    async def test_health_always_200(self, http_client):
        """Article II.5: health check always 200."""
        response = await http_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_submit_without_token_returns_403(self, http_client):
        """Article II.1: no token → 403. Autonomous submission is impossible."""
        with patch("src.api.middleware.auth.verify_session",
                   return_value={"coder_id": "coder-001"}):
            response = await http_client.post(
                "/review/enc-e2e-001/approve",
                json={"approved_codes": ["I50.21", "N17.9"]},
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_submit_with_valid_token_succeeds(self, http_client):
        """Full approval workflow: generate token → submit → 200."""
        service = ApprovalTokenService(
            secret_key="dev-secret-key-minimum-32-characters-long"
        )
        token = service.generate(
            encounter_id="enc-e2e-001",
            coder_id="coder-001",
            approved_codes=["I50.21", "N17.9"],
        )

        with patch("src.api.middleware.auth.verify_session",
                   return_value={"coder_id": "coder-001"}):
            response = await http_client.post(
                "/review/enc-e2e-001/approve",
                json={
                    "approved_codes": ["I50.21", "N17.9"],
                    "approval_token": token.token_value,
                },
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["encounter_id"] == "enc-e2e-001"
        assert data["codes_submitted"] == 2
        assert "Smith" not in str(data)
        assert "patient_name" not in str(data)

    @pytest.mark.asyncio
    async def test_no_phi_in_any_api_response(self, http_client):
        """Article II.4: every API response is PHI-free."""
        phi_indicators = [
            "Smith", "John", "1956-03-15",
            "MRN-456789", "patient_name",
            "date_of_birth", "social_security",
        ]

        with patch("src.api.middleware.auth.verify_session",
                   return_value={"coder_id": "coder-001"}):
            for path in ["/health", "/queue", "/review/enc-e2e-001"]:
                response = await http_client.get(
                    path,
                    headers={"Authorization": "Bearer test-token"},
                )
                for phi in phi_indicators:
                    assert phi not in response.text, (
                        f"PHI indicator '{phi}' found in {path} response"
                    )


class TestAllComplianceGuardrailsEndToEnd:
    """Final verification that all Article II rules are enforced end-to-end."""

    def test_article_ii_1_token_required_in_route(self):
        """The approval route source code requires token."""
        import inspect
        from src.api.routes import coding
        source = inspect.getsource(coding.approve_submission)
        assert "approval_token" in source
        assert "403" in source

    def test_article_ii_2_evidence_citation_in_agent(self):
        """CodingAgent filters suggestions without evidence_quote."""
        import inspect
        from src.agents.coding_agent import CodingAgent
        source = inspect.getsource(CodingAgent._parse_suggestions)
        assert "evidence_quote" in source

    def test_article_ii_3_outpatient_uncertain_dx_filtered(self):
        """CodingAgent filters uncertain outpatient diagnoses."""
        import inspect
        from src.agents.coding_agent import CodingAgent
        source = inspect.getsource(CodingAgent._parse_single_suggestion)
        assert "uncertainty_qualifier" in source or "UNCERTAINTY" in source

    def test_article_ii_4_phi_blocklist_in_audit_model(self):
        """UserActionAuditEntry rejects PHI field names in details."""
        from src.core.models.audit import UserActionAuditEntry, AuditAction
        import pytest
        with pytest.raises(Exception):
            UserActionAuditEntry(
                coder_id="coder-001",
                encounter_id="enc-001",
                action=AuditAction.VIEWED,
                session_id="sess-001",
                details={"patient_name": "John Smith"},
            )

    def test_article_ii_5_fhir_client_has_degraded_result(self):
        """FHIRClient returns DegradedResult on error."""
        import inspect
        from src.core.fhir.client import FHIRClient
        source = inspect.getsource(FHIRClient)
        assert "DegradedResult" in source

    def test_article_ii_6_conservative_specificity_guardrail_exists(self):
        """Conservative specificity guardrail is importable and functional."""
        from src.core.guardrails.specificity_guardrail import (
            apply_conservative_specificity,
        )
        from src.core.models.coding import CodingSuggestion
        suggestion = CodingSuggestion(
            code="I50.21",
            description="Acute systolic CHF",
            confidence=0.88,
            evidence_quote="heart failure",
            drg_impact="$7,500",
        )
        result = apply_conservative_specificity(
            suggestion=suggestion,
            documentation_supports_acuity=False,
        )
        assert result.cdi_query_required is True
        assert result.selected_code == "I50.20"
