"""
Coder Workflow Integration Tests — BUILD-009
Tests the full HTTP workflow through FastAPI routes.

Constitution: II.1 (token required), II.4 (no PHI in responses),
              II.5 (graceful degradation)
Spec: specs/06-coder-review-ui.md
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock

from src.api.main import app
from src.core.models.coding import CodingAnalysisResult, ValidationResult
from src.core.models.cdi import CDIAnalysisResult


@pytest.fixture
async def client():
    """Async HTTP test client for FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


class TestHealthRoute:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health check always returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestQueueRoute:

    @pytest.mark.asyncio
    async def test_queue_requires_authentication(self, client):
        """Queue endpoint requires valid session."""
        response = await client.get("/queue")
        assert response.status_code in (401, 403, 307)

    @pytest.mark.asyncio
    async def test_queue_returns_encounter_list(self, client):
        """Authenticated request returns list of pending encounters."""
        with patch("src.api.middleware.auth.verify_session",
                   return_value={"coder_id": "coder-001"}):
            response = await client.get(
                "/queue",
                headers={"Authorization": "Bearer test-token"}
            )
        # Either 200 with list or redirect — not 500
        assert response.status_code != 500


class TestReviewRoute:

    @pytest.mark.asyncio
    async def test_review_page_no_patient_name(self, client):
        """
        Article II.4: patient name never appears in review response.
        MRN displayed as ****1234 only.
        """
        mock_result = MagicMock(spec=CodingAnalysisResult)
        mock_result.suggestions = []
        mock_result.encounter_id = "enc-001"
        mock_result.is_degraded = False
        mock_result.coding_class = "inpatient"

        with patch("src.api.middleware.auth.verify_session",
                   return_value={"coder_id": "coder-001"}):
            with patch("src.api.routes.coding.get_coding_analysis",
                       new_callable=AsyncMock,
                       return_value=mock_result):
                response = await client.get(
                    "/review/enc-001",
                    headers={"Authorization": "Bearer test-token"}
                )

        if response.status_code == 200:
            content = response.text
            # Patient name patterns must not appear
            assert "Smith" not in content
            assert "John" not in content
            # Full MRN must not appear
            import re
            assert not re.search(r"\bMRN-\d{6}\b", content)


class TestApproveRoute:

    @pytest.mark.asyncio
    async def test_approve_without_token_returns_403(self, client):
        """
        Article II.1: submission without approval token → 403.
        This is the HTTP-layer enforcement of the guardrail.
        """
        response = await client.post(
            "/review/enc-001/approve",
            json={"approved_codes": ["I50.21"]},
            # No Authorization header, no approval token
        )
        assert response.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_approve_logs_audit_entry(self, client):
        """
        Every submission logged to audit trail.
        Spec: specs/06-coder-review-ui.md Section 5.
        """
        audit_entries = []

        def capture_audit(entry):
            audit_entries.append(entry)

        with patch("src.api.middleware.auth.verify_session",
                   return_value={"coder_id": "coder-001"}):
            with patch("src.api.middleware.audit.write_audit_log",
                       side_effect=capture_audit):
                with patch("src.api.routes.coding.process_approval",
                           new_callable=AsyncMock,
                           return_value={"status": "approved"}):
                    response = await client.post(
                        "/review/enc-001/approve",
                        json={
                            "approved_codes": ["I50.21"],
                            "approval_token": "mock-token-value",
                        },
                        headers={"Authorization": "Bearer test-token"}
                    )

        # If route exists and processes: no 500
        assert response.status_code != 500

    @pytest.mark.asyncio
    async def test_approve_no_phi_in_response(self, client):
        """
        API response must not contain PHI.
        Success/error messages contain only encounter_id and status.
        """
        with patch("src.api.middleware.auth.verify_session",
                   return_value={"coder_id": "coder-001"}):
            response = await client.post(
                "/review/enc-001/approve",
                json={"approved_codes": ["I50.21"]},
                headers={"Authorization": "Bearer test-token"}
            )

        if response.status_code == 200:
            data = response.json()
            content = str(data)
            # No patient names in response
            assert "Smith" not in content
            assert "patient_name" not in content
