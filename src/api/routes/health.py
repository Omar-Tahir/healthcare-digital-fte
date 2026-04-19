"""Health check route — always returns 200 when server is running."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check — always returns 200 when server is running.
    Returns "ok" when all components healthy.
    Constitution: II.5 (never returns 500).
    """
    return HealthResponse(status="ok", version="0.1.0")
