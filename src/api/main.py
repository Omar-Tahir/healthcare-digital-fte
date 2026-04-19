"""
Healthcare Digital FTE — FastAPI Application

Routes:
  GET  /           → demo UI (index.html)
  GET  /health
  GET  /queue
  GET  /review/{encounter_id}
  POST /review/{encounter_id}/approve
  POST /api/v1/coding/analyze

Constitution: II.1 (approval token required),
              II.4 (no PHI in any response),
              II.5 (graceful degradation — /health always 200),
              III.8 (FastAPI with Pydantic models)
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import health, coding

app = FastAPI(
    title="Healthcare Digital FTE",
    version="0.1.0",
    description=(
        "AI-powered medical coding suggestion and CDI system. "
        "All clinical suggestions require human coder approval."
    ),
)

# Static assets (CSS, JS if any) — served at /static/*
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", include_in_schema=False)
async def demo_ui() -> FileResponse:
    """Serve the single-page demo interface."""
    return FileResponse(os.path.join(_static_dir, "index.html"))


# CORS — same-origin only in production; explicit whitelist avoids wildcard
_allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins if o.strip()]
if not _allowed_origins:
    _allowed_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # CSP: allow only same-origin scripts and styles (inline scripts needed for demo UI)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'"
    )
    return response


app.include_router(health.router)
app.include_router(coding.router)
