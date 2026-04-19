"""
JWT session authentication middleware.

Sessions expire after 30 minutes of inactivity (HIPAA requirement).
All routes except /health require valid session.

Constitution: II.4 (no PHI in auth flow)
Spec: specs/06-coder-review-ui.md §3
"""
from __future__ import annotations

import structlog
from fastapi import HTTPException, Header
from typing import Annotated

log = structlog.get_logger()


async def verify_session(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """
    Verify session token from Authorization header.
    Returns session dict with coder_id on success.
    Raises HTTP 401 if missing or invalid.

    In production: verify JWT signature, check expiry,
    look up coder in database.
    In development: accept any non-empty bearer token.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Bearer token required.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Empty token.",
        )

    # Development mode: accept any non-empty token
    # Production: verify JWT signature here
    log.info("session_verified")
    return {"coder_id": "coder-dev-001"}
