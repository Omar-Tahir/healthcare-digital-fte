"""
Approval Token Tests — BUILD-009
Written BEFORE implementation (TDD red phase).

The approval token is the data-layer enforcement of
constitution Article II.1 (no autonomous claim submission).
Without a valid token, write_draft_claim cannot proceed.

Every test here corresponds to a guardrail in
specs/03-compliance-guardrail-architecture.md G-HARD-001.
"""
import pytest
from datetime import datetime, timezone, timedelta

from src.api.security.approval_token import (
    ApprovalTokenService,
    TokenValidationError,
)
from src.core.models.guardrails import ApprovalToken


class TestApprovalTokenGeneration:

    @pytest.fixture
    def service(self):
        return ApprovalTokenService(secret_key="test-secret-key-32-chars-minimum")

    def test_token_generated_with_required_fields(self, service):
        """Generated token has all required fields."""
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21", "E11.22"],
        )
        assert isinstance(token, ApprovalToken)
        assert token.encounter_id == "enc-001"
        assert token.coder_id == "coder-001"
        assert token.token_value
        assert token.approved_codes_hash
        assert token.expires_at > datetime.now(timezone.utc)
        assert token.is_consumed is False

    def test_token_expires_in_15_minutes(self, service):
        """Token expiry is exactly 15 minutes from creation."""
        before = datetime.now(timezone.utc)
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21"],
        )
        after = datetime.now(timezone.utc)

        expected_expiry_low = before + timedelta(minutes=14, seconds=59)
        expected_expiry_high = after + timedelta(minutes=15, seconds=1)
        assert token.expires_at >= expected_expiry_low
        assert token.expires_at <= expected_expiry_high

    def test_token_value_is_hmac_sha256(self, service):
        """Token value is a hex string (HMAC-SHA256 output)."""
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21"],
        )
        # HMAC-SHA256 produces 64-char hex string
        assert len(token.token_value) == 64
        assert all(c in "0123456789abcdef" for c in token.token_value)

    def test_different_code_sets_produce_different_tokens(self, service):
        """Code set hash ensures token is bound to specific codes."""
        token_a = service.generate("enc-001", "coder-001", ["I50.21"])
        token_b = service.generate("enc-001", "coder-001", ["I50.21", "E11.22"])
        assert token_a.approved_codes_hash != token_b.approved_codes_hash
        assert token_a.token_value != token_b.token_value


class TestApprovalTokenValidation:

    @pytest.fixture
    def service(self):
        return ApprovalTokenService(secret_key="test-secret-key-32-chars-minimum")

    def test_valid_token_validates_successfully(self, service):
        """Valid token, correct codes, not expired → validates."""
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21", "E11.22"],
        )
        # Should not raise
        service.validate(
            token=token,
            encounter_id="enc-001",
            approved_codes=["I50.21", "E11.22"],
        )

    def test_expired_token_raises_error(self, service):
        """
        Token older than 15 minutes raises TokenValidationError.
        Article II.1: expired token = no claim submission.
        """
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21"],
        )
        # Backdate the expiry
        expired_token = token.model_copy(update={
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)
        })
        with pytest.raises(TokenValidationError, match="expired"):
            service.validate(
                token=expired_token,
                encounter_id="enc-001",
                approved_codes=["I50.21"],
            )

    def test_consumed_token_raises_error(self, service):
        """
        Single-use: consumed token raises TokenValidationError.
        Article II.1: same token cannot submit two claims.
        """
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21"],
        )
        consumed_token = token.model_copy(update={"is_consumed": True})
        with pytest.raises(TokenValidationError, match="consumed"):
            service.validate(
                token=consumed_token,
                encounter_id="enc-001",
                approved_codes=["I50.21"],
            )

    def test_wrong_encounter_id_raises_error(self, service):
        """Token generated for enc-001 cannot be used for enc-002."""
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21"],
        )
        with pytest.raises(TokenValidationError, match="encounter"):
            service.validate(
                token=token,
                encounter_id="enc-002",  # wrong encounter
                approved_codes=["I50.21"],
            )

    def test_modified_code_set_raises_error(self, service):
        """
        Token bound to [I50.21]. Submission with [I50.21, E11.22]
        raises TokenValidationError — code set changed after token issued.
        Article II.1: coder cannot add codes after token generation.
        """
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21"],
        )
        with pytest.raises(TokenValidationError, match="code"):
            service.validate(
                token=token,
                encounter_id="enc-001",
                approved_codes=["I50.21", "E11.22"],  # extra code
            )

    def test_tampered_token_value_raises_error(self, service):
        """HMAC verification fails for tampered token."""
        token = service.generate(
            encounter_id="enc-001",
            coder_id="coder-001",
            approved_codes=["I50.21"],
        )
        tampered = token.model_copy(update={
            "token_value": "a" * 64  # wrong HMAC
        })
        with pytest.raises(TokenValidationError, match="invalid"):
            service.validate(
                token=tampered,
                encounter_id="enc-001",
                approved_codes=["I50.21"],
            )
