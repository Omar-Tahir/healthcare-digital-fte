"""
Claim Approval Token Guardrail — G-HARD-001.

Enforces constitution Article II.1: No claim submission without human approval.
Every FHIR Claim write must be preceded by a valid approval token from a
credentialed coder.

The token is a simple HMAC-SHA256 string bound to:
  - coder_id (who approved)
  - encounter_id (which encounter)
  - code_set_hash (SHA-256 of sorted approved codes)
  - issued_at (timestamp — expires after 15 minutes)

The _TOKEN_STORE persists consumed tokens to prevent replay attacks.
In production: replace with Redis.

Constitution: Article II.1
Spec: specs/06-coder-review-ui.md §4
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import structlog

from src.core.exceptions import HumanApprovalRequiredError

log = structlog.get_logger()

_GUARDRAIL_ID = "G-HARD-001"
_TOKEN_LIFETIME_SECONDS = 900  # 15 minutes

def _get_secret_key() -> bytes:
    """Load claim guardrail secret from env. Falls back to a dev-only default."""
    import os
    key = os.getenv("CLAIM_TOKEN_SECRET_KEY", "")
    if key:
        return key.encode()
    import warnings
    warnings.warn(
        "CLAIM_TOKEN_SECRET_KEY not set — using insecure dev default. "
        "Set this env var before deploying to production.",
        stacklevel=2,
    )
    return b"dev-only-claim-secret-not-for-production"

# In-memory token store: {token_value: {encounter_id, code_set_hash, consumed}}
_TOKEN_STORE: dict[str, dict] = {}


def _hash_code_set(code_set: list[str]) -> str:
    """SHA-256 of sorted code list — order-independent."""
    sorted_codes = sorted(set(code_set))
    return hashlib.sha256(
        json.dumps(sorted_codes, separators=(",", ":")).encode()
    ).hexdigest()


def generate_approval_token(
    coder_id: str,
    encounter_id: str,
    code_set: list[str],
) -> str:
    """
    Generate a new approval token for the given coder, encounter, and code set.
    Returns a 64-char HMAC-SHA256 hex string.
    Stores metadata in _TOKEN_STORE for validation.
    """
    issued_at = int(time.time())
    code_set_hash = _hash_code_set(code_set)
    message = f"{coder_id}:{encounter_id}:{issued_at}:{code_set_hash}"
    token_value = hmac.new(_get_secret_key(), message.encode(), hashlib.sha256).hexdigest()

    _TOKEN_STORE[token_value] = {
        "coder_id": coder_id,
        "encounter_id": encounter_id,
        "code_set_hash": code_set_hash,
        "issued_at": issued_at,
        "consumed": False,
    }

    log.info(
        "approval_token_generated",
        guardrail_id=_GUARDRAIL_ID,
        encounter_id=encounter_id,
        coder_id=coder_id,
    )
    return token_value


def validate_approval_token(
    token: str | None,
    encounter_id: str,
    code_set: list[str],
    _issued_at_override: int | None = None,
) -> bool:
    """
    Validate approval token. Returns True if valid.
    Raises HumanApprovalRequiredError on any failure.

    _issued_at_override: testing parameter. Negative means seconds in the past.
    e.g. -960 = token was issued 960 seconds ago (expired).

    Checks: token present → not expired → not consumed → encounter match → code hash match.
    """
    if token is None:
        raise HumanApprovalRequiredError(
            guardrail_id=_GUARDRAIL_ID,
            reason="Approval token is required. No token provided.",
        )

    # Check expiry via testing override
    if _issued_at_override is not None:
        age_seconds = abs(_issued_at_override)
        if age_seconds > _TOKEN_LIFETIME_SECONDS:
            raise HumanApprovalRequiredError(
                guardrail_id=_GUARDRAIL_ID,
                reason=f"Token has expired (issued {age_seconds}s ago; limit {_TOKEN_LIFETIME_SECONDS}s).",
            )

    # Look up token in store
    entry = _TOKEN_STORE.get(token)
    if entry is None:
        raise HumanApprovalRequiredError(
            guardrail_id=_GUARDRAIL_ID,
            reason="Token not found or invalid.",
        )

    # Check real expiry using stored issued_at
    if _issued_at_override is None:
        age = int(time.time()) - entry["issued_at"]
        if age > _TOKEN_LIFETIME_SECONDS:
            raise HumanApprovalRequiredError(
                guardrail_id=_GUARDRAIL_ID,
                reason=f"Token has expired ({age}s elapsed; limit {_TOKEN_LIFETIME_SECONDS}s).",
            )

    # Single-use check
    if entry["consumed"]:
        raise HumanApprovalRequiredError(
            guardrail_id=_GUARDRAIL_ID,
            reason="Token has already been consumed. Cannot reuse an approval token.",
        )

    # Encounter match
    if entry["encounter_id"] != encounter_id:
        raise HumanApprovalRequiredError(
            guardrail_id=_GUARDRAIL_ID,
            reason=f"Token encounter ID mismatch.",
        )

    # Code set match
    submitted_hash = _hash_code_set(code_set)
    if submitted_hash != entry["code_set_hash"]:
        raise HumanApprovalRequiredError(
            guardrail_id=_GUARDRAIL_ID,
            reason="Submitted code set hash does not match approved code set.",
        )

    # Mark consumed (single-use enforcement)
    _TOKEN_STORE[token]["consumed"] = True

    log.info(
        "approval_token_validated",
        guardrail_id=_GUARDRAIL_ID,
        encounter_id=encounter_id,
    )
    return True
