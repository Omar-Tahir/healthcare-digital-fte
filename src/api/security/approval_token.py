"""
Approval Token Service — enforces constitution Article II.1.

The approval token is the single mechanism that prevents
autonomous claim submission. Without a valid token,
the FHIR Claim write cannot occur.

Token specification (from specs/06-coder-review-ui.md Section 4):
  - HMAC-SHA256(encounter_id + coder_id + timestamp + codes_hash)
  - Single-use: consumed on first successful validation
  - Expires: 15 minutes from generation
  - Bound to specific code set: cannot change codes after token issued
  - Timestamp stored in token (created_at) to enable HMAC re-derivation

Constitution: Article II.1
Spec: specs/06-coder-review-ui.md §4
"""
from __future__ import annotations

import hashlib
import hmac
import json
import structlog
from datetime import datetime, timezone, timedelta

from src.core.models.guardrails import ApprovalToken

log = structlog.get_logger()

TOKEN_LIFETIME_MINUTES = 15


class TokenValidationError(Exception):
    """
    Raised when approval token validation fails.
    The claim submission MUST stop when this is raised.
    Constitution Article II.1.
    """
    pass


class ApprovalTokenService:
    """
    Generates and validates approval tokens.

    Tokens are HMAC-SHA256 signed using a server secret.
    They cannot be forged without the secret key.
    They expire after 15 minutes.
    They are single-use — consumed on first validation.

    Usage:
        service = ApprovalTokenService(secret_key=settings.SECRET_KEY)
        token = service.generate(encounter_id, coder_id, codes)
        service.validate(token, encounter_id, codes)  # raises if invalid
    """

    def __init__(self, secret_key: str):
        if len(secret_key) < 32:
            raise ValueError(
                "Secret key must be at least 32 characters. "
                "Generate with: python -m secrets token_hex 32"
            )
        self._secret = secret_key.encode()

    def generate(
        self,
        encounter_id: str,
        coder_id: str,
        approved_codes: list[str],
    ) -> ApprovalToken:
        """
        Generate a new approval token bound to these specific codes.

        The token value is HMAC-SHA256 over:
            encounter_id + coder_id + timestamp + sorted_codes_hash

        The approved_codes_hash is SHA-256 of the sorted code list.
        Sorting ensures [A, B] and [B, A] produce the same hash.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=TOKEN_LIFETIME_MINUTES)
        timestamp = str(int(now.timestamp()))

        codes_hash = self._hash_codes(approved_codes)
        message = f"{encounter_id}:{coder_id}:{timestamp}:{codes_hash}"
        token_value = hmac.new(
            self._secret,
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        log.info(
            "approval_token_generated",
            encounter_id=encounter_id,
            coder_id=coder_id,
            code_count=len(approved_codes),
            expires_at=expires_at.isoformat(),
            # Never log the codes themselves — clinical content
        )

        return ApprovalToken(
            token_value=token_value,
            encounter_id=encounter_id,
            coder_id=coder_id,
            approved_codes_hash=codes_hash,
            created_at=now,
            expires_at=expires_at,
            is_consumed=False,
        )

    def validate(
        self,
        token: ApprovalToken,
        encounter_id: str,
        approved_codes: list[str],
    ) -> None:
        """
        Validate token. Raises TokenValidationError if invalid.

        Checks (in order):
        1. Not expired
        2. Not already consumed (single-use)
        3. Encounter ID matches
        4. Code set matches (hash comparison)
        5. HMAC signature is valid (re-derived from stored created_at)

        If all checks pass: token is ready to be marked consumed.
        The caller is responsible for persisting the consumed state.
        """
        now = datetime.now(timezone.utc)

        # Check 1: Expiry
        if now >= token.expires_at:
            log.warning(
                "approval_token_expired",
                encounter_id=encounter_id,
                expired_at=token.expires_at.isoformat(),
            )
            raise TokenValidationError(
                "Token has expired. Generate a new approval token."
            )

        # Check 2: Single-use
        if token.is_consumed:
            log.warning(
                "approval_token_already_consumed",
                encounter_id=encounter_id,
            )
            raise TokenValidationError(
                "Token has already been consumed. "
                "Cannot reuse an approval token."
            )

        # Check 3: Encounter match
        if token.encounter_id != encounter_id:
            log.warning(
                "approval_token_encounter_mismatch",
                token_encounter=token.encounter_id,
                request_encounter=encounter_id,
            )
            raise TokenValidationError(
                "Token encounter ID does not match request encounter."
            )

        # Check 4: Code set match
        submitted_hash = self._hash_codes(approved_codes)
        if submitted_hash != token.approved_codes_hash:
            log.warning(
                "approval_token_code_set_mismatch",
                encounter_id=encounter_id,
            )
            raise TokenValidationError(
                "Submitted code set does not match approved code set. "
                "Generate a new token if codes were changed."
            )

        # Check 5: HMAC re-derivation using stored created_at timestamp
        timestamp = str(int(token.created_at.timestamp()))
        message = (
            f"{token.encounter_id}:{token.coder_id}:{timestamp}"
            f":{token.approved_codes_hash}"
        )
        expected = hmac.new(
            self._secret,
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(token.token_value, expected):
            log.warning(
                "approval_token_hmac_invalid",
                encounter_id=encounter_id,
            )
            raise TokenValidationError(
                "Token value is invalid — tampered or forged."
            )

        log.info(
            "approval_token_validated",
            encounter_id=encounter_id,
            coder_id=token.coder_id,
        )

    @staticmethod
    def _hash_codes(codes: list[str]) -> str:
        """
        SHA-256 hash of the sorted code list.
        Sorting ensures order-independence:
        [I50.21, E11.22] == [E11.22, I50.21]
        """
        sorted_codes = sorted(set(codes))
        codes_json = json.dumps(sorted_codes, separators=(",", ":"))
        return hashlib.sha256(codes_json.encode()).hexdigest()
