"""
Coding review routes.

GET  /queue                 — work queue of pending encounters
GET  /review/{encounter_id} — main coding interface
POST /review/{encounter_id}/approve — submit approved codes

Constitution: II.1 (approval token required for submit),
              II.4 (no PHI in any response),
              II.5 (graceful degradation — never 500)
Spec: specs/06-coder-review-ui.md §1
"""
from __future__ import annotations

import re
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from typing import Annotated

from src.api.middleware.auth import verify_session
from src.api.middleware.audit import write_audit_log, create_audit_entry
from src.api.security.approval_token import (
    ApprovalTokenService,
    TokenValidationError,
)
from src.core.models.audit import AuditAction
from src.core.models.encounter import EncounterContext

log = structlog.get_logger()
router = APIRouter()

def _get_token_service() -> ApprovalTokenService:
    """Load approval token secret from env at call time. Never hardcoded."""
    import os
    key = os.getenv("APPROVAL_TOKEN_SECRET_KEY", "")
    if not key:
        import warnings
        warnings.warn(
            "APPROVAL_TOKEN_SECRET_KEY not set — using insecure dev default.",
            stacklevel=2,
        )
        key = "dev-only-approval-secret-not-for-production-min-32ch"
    return ApprovalTokenService(secret_key=key)


class ApproveRequest(BaseModel):
    approved_codes: list[str]
    approval_token: str | None = None


class ApproveResponse(BaseModel):
    status: str
    encounter_id: str
    codes_submitted: int
    message: str


async def get_coding_analysis(encounter_id: str):
    """Stub — returns empty result in development."""
    from src.core.models.coding import CodingAnalysisResult, ValidationResult
    return CodingAnalysisResult(
        encounter_id=encounter_id,
        coding_class="inpatient",
        suggestions=[],
        validation_result=ValidationResult(is_valid=True),
    )


async def process_approval(encounter_id: str, codes: list[str]) -> dict:
    """Stub — in production writes FHIR Claim draft (status=draft)."""
    return {"status": "approved", "encounter_id": encounter_id}


@router.get("/queue")
async def get_queue(
    session: Annotated[dict, Depends(verify_session)],
) -> dict:
    """
    Return list of encounters pending coding review.
    Patient names never included — encounter IDs only.
    Article II.4: no PHI in response.
    """
    return {
        "coder_id": session["coder_id"],
        "pending_count": 0,
        "encounters": [],
    }


@router.get("/review/{encounter_id}")
async def get_review(
    encounter_id: str,
    session: Annotated[dict, Depends(verify_session)],
) -> dict:
    """
    Return coding analysis for a specific encounter.
    No patient name in response — encounter_id only.
    Article II.4: no PHI in response.
    """
    write_audit_log(create_audit_entry(
        coder_id=session["coder_id"],
        encounter_id=encounter_id,
        action=AuditAction.VIEWED,
    ))

    result = await get_coding_analysis(encounter_id)

    return {
        "encounter_id": encounter_id,
        "coding_class": result.coding_class,
        "suggestion_count": len(result.suggestions),
        "suggestions": [
            {
                "code": s.code,
                "description": s.description,
                "confidence": s.confidence,
                "evidence_quote": s.evidence_quote,
                "drg_impact": s.drg_impact,
                "requires_senior_review": s.requires_senior_review,
                "compliance_review_required": s.compliance_review_required,
            }
            for s in result.suggestions
        ],
        "is_degraded": result.is_degraded,
    }


@router.post(
    "/review/{encounter_id}/approve",
    response_model=ApproveResponse,
)
async def approve_submission(
    encounter_id: str,
    request: ApproveRequest,
    session: Annotated[dict, Depends(verify_session)],
) -> ApproveResponse:
    """
    Submit approved codes for a coding encounter.

    Article II.1: approval_token REQUIRED.
    Without a valid token: 403 Forbidden.
    Token format validated; full HMAC validation requires token store (BUILD-010+).
    """
    if not request.approval_token:
        write_audit_log(create_audit_entry(
            coder_id=session["coder_id"],
            encounter_id=encounter_id,
            action=AuditAction.TOKEN_REJECTED,
            details={"reason": "missing_token"},
        ))
        raise HTTPException(
            status_code=403,
            detail="Approval token required. "
                   "Generate token from the review interface.",
        )

    try:
        _validate_token_format(request.approval_token)
    except TokenValidationError as e:
        write_audit_log(create_audit_entry(
            coder_id=session["coder_id"],
            encounter_id=encounter_id,
            action=AuditAction.TOKEN_REJECTED,
            details={"reason": "invalid_format"},
        ))
        raise HTTPException(status_code=403, detail=str(e))

    write_audit_log(create_audit_entry(
        coder_id=session["coder_id"],
        encounter_id=encounter_id,
        action=AuditAction.TOKEN_VALIDATED,
        details={"code_count": len(request.approved_codes)},
    ))

    await process_approval(encounter_id, request.approved_codes)

    for code in request.approved_codes:
        write_audit_log(create_audit_entry(
            coder_id=session["coder_id"],
            encounter_id=encounter_id,
            action=AuditAction.ACCEPTED_CODE,
            code=code,
        ))

    write_audit_log(create_audit_entry(
        coder_id=session["coder_id"],
        encounter_id=encounter_id,
        action=AuditAction.SUBMITTED_CLAIM,
        details={"code_count": len(request.approved_codes)},
    ))

    log.info(
        "claim_submitted",
        encounter_id=encounter_id,
        coder_id=session["coder_id"],
        code_count=len(request.approved_codes),
        # Never log the codes themselves — clinical content
    )

    return ApproveResponse(
        status="submitted",
        encounter_id=encounter_id,
        codes_submitted=len(request.approved_codes),
        message="Codes submitted for review. Draft claim created.",
    )


_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]+$")

class AnalyzeRequest(BaseModel):
    encounter_id: str = Field(min_length=1, max_length=255)
    encounter_setting: str = Field(min_length=1, max_length=50)
    note_text: str = Field(min_length=1, max_length=50_000)  # ~10 pages — prevents memory abuse

    @field_validator("encounter_id")
    @classmethod
    def encounter_id_safe(cls, v: str) -> str:
        if not _SAFE_ID_RE.match(v):
            raise ValueError("encounter_id must contain only alphanumeric characters, hyphens, or underscores")
        return v

    @field_validator("encounter_setting")
    @classmethod
    def encounter_setting_valid(cls, v: str) -> str:
        allowed = {"inpatient", "outpatient", "observation", "ambulatory"}
        if v.lower() not in allowed:
            raise ValueError(f"encounter_setting must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


# Simple in-memory rate limiter: max 20 requests per IP per minute
import time as _time
_rate_store: dict[str, list[float]] = {}
_RATE_LIMIT = 20
_RATE_WINDOW = 60.0

def _check_rate_limit(client_ip: str) -> None:
    now = _time.monotonic()
    window_start = now - _RATE_WINDOW
    hits = _rate_store.get(client_ip, [])
    hits = [t for t in hits if t > window_start]
    if len(hits) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before analyzing another note.",
        )
    hits.append(now)
    _rate_store[client_ip] = hits


@router.post("/api/v1/coding/analyze")
async def coding_analyze(
    http_request: Request,
    request: AnalyzeRequest,
    session: Annotated[dict, Depends(verify_session)],
) -> dict:
    """
    Full coding analysis pipeline endpoint.
    Always returns 200 — returns is_degraded=True on any failure.
    Constitution: II.5 (graceful degradation — never 500).
    Requires valid session (verify_session).
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    _check_rate_limit(client_ip)
    from src.agents.coding_agent import CodingAgent
    from src.core.models.fhir import DegradedResult

    try:
        agent = CodingAgent()
        encounter = EncounterContext(
            encounter_id=request.encounter_id,
            encounter_setting=request.encounter_setting,
            note_text=request.note_text,
        )
        result = await agent.analyze(encounter)

        if isinstance(result, DegradedResult):
            return {
                "encounter_id": request.encounter_id,
                "is_degraded": True,
                "suggestions": [],
                "error_code": result.error_code,
            }

        return {
            "encounter_id": result.encounter_id,
            "coding_class": result.coding_class,
            "is_degraded": result.is_degraded,
            "suggestion_count": len(result.suggestions),
            "suggestions": [
                {
                    "code": s.code,
                    "description": s.description,
                    "confidence": s.confidence,
                    "evidence_quote": s.evidence_quote,
                    "drg_impact": s.drg_impact,
                    "drg_revenue_delta": s.drg_revenue_delta,
                    "is_mcc": s.is_mcc,
                    "is_cc": s.is_cc,
                    "requires_senior_review": s.requires_senior_review,
                    "compliance_review_required": s.compliance_review_required,
                    "routing_queue": s.routing_queue,
                }
                for s in result.suggestions
            ],
        }
    except Exception as e:
        log.warning(
            "coding_analyze_route_failed",
            error_type=type(e).__name__,
            encounter_id=request.encounter_id,
        )
        return {
            "encounter_id": request.encounter_id,
            "is_degraded": True,
            "suggestions": [],
        }


def _validate_token_format(token_value: str) -> None:
    """
    Validate token format: 64-char lowercase hex (HMAC-SHA256 output).
    Full HMAC validation requires token store lookup (BUILD-010+).
    """
    if len(token_value) != 64:
        raise TokenValidationError(
            "Token value is invalid — must be 64-character hex string."
        )
    if not all(c in "0123456789abcdef" for c in token_value):
        raise TokenValidationError(
            "Token value is invalid — non-hex characters detected."
        )
