"""
FHIR R4 client for Epic EHR integration.

Every public method returns the appropriate Pydantic model OR DegradedResult.
Never raises to the caller — constitution Article II.5.
No PHI in any log call — constitution Article II.4.
Draft claim status is always enforced — constitution Article II.1.

Spec: specs/05-fhir-integration.md
Skill: docs/skills/fhir-r4-integration.md
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from src.core.fhir.auth import FHIRAuthenticator
from src.core.fhir.resources import (
    parse_document_reference,
    parse_encounter,
    parse_observation,
    parse_patient,
)
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
    FHIRObservation,
    FHIRPatient,
)

log = structlog.get_logger()

# HTTP status codes that warrant a retry with backoff.
# Per docs/skills/fhir-r4-integration.md Section 4.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
RETRY_BACKOFF_SECONDS: list[float] = [1.0, 2.0, 4.0]


class FHIRClient:
    """
    Async FHIR R4 client with automatic token management,
    HTTP retry logic for transient errors, and graceful degradation.

    Usage:
        client = FHIRClient(base_url=..., client_id=..., private_key_pem=...)
        result = await client.get_patient("patient-123")
        if isinstance(result, DegradedResult):
            # handle degraded mode — workflow continues without AI
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        private_key_pem: str,
        kid: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # Build token URL from base URL (split on /api/ to get the host)
        host = base_url.split("/api/")[0] if "/api/" in base_url else base_url
        self._auth = FHIRAuthenticator(
            client_id=client_id,
            token_url=f"{host}/oauth2/token",
            private_key_pem=private_key_pem,
            kid=kid,
        )
        self._http = httpx.AsyncClient(timeout=30.0)

    # ─── Public methods ──────────────────────────────────────────────────────

    async def get_patient(
        self,
        patient_id: str,
    ) -> FHIRPatient | DegradedResult:
        """
        Retrieve a patient by FHIR ID.

        Returns FHIRPatient (id only — PHI fields excluded from model).
        Returns DegradedResult on any network or HTTP error.
        """
        raw = await self._get(f"/Patient/{patient_id}")
        if isinstance(raw, DegradedResult):
            return raw
        try:
            return parse_patient(raw)
        except Exception as e:
            log.warning("patient_parse_failed", error_type=type(e).__name__)
            return DegradedResult(
                error_code="FHIR_PATIENT_PARSE_FAILED",
                error_message=f"Parse error: {type(e).__name__}",
            )

    async def get_encounter(
        self,
        encounter_id: str,
    ) -> FHIREncounter | DegradedResult:
        """
        Retrieve an encounter by FHIR ID.

        The returned FHIREncounter carries encounter_class which
        determines whether inpatient or outpatient coding rules apply.
        OBS class → EncounterClass.OBSERVATION → outpatient rules.
        """
        raw = await self._get(f"/Encounter/{encounter_id}")
        if isinstance(raw, DegradedResult):
            return raw
        try:
            return parse_encounter(raw)
        except Exception as e:
            log.warning("encounter_parse_failed", error_type=type(e).__name__)
            return DegradedResult(
                error_code="FHIR_ENCOUNTER_PARSE_FAILED",
                error_message=f"Parse error: {type(e).__name__}",
            )

    async def get_clinical_notes(
        self,
        patient_id: str,
        encounter_id: str,
        note_types: list[str] | None = None,
    ) -> list[FHIRDocumentReference]:
        """
        Retrieve all clinical notes for a patient encounter.

        Returns empty list on any error (Article II.5 — workflow continues).
        Notes with unextractable content (e.g. PDF) are included with
        note_text=None — the coding agent handles degraded note data.
        """
        params: dict[str, str] = {
            "patient": patient_id,
            "encounter": encounter_id,
            "category": "clinical-note",
        }
        if note_types:
            params["type"] = ",".join(note_types)

        first_page = await self._get("/DocumentReference", params=params)
        if isinstance(first_page, DegradedResult):
            log.warning(
                "clinical_notes_fetch_degraded",
                error_code=first_page.error_code,
                encounter_id=encounter_id,
            )
            return []

        all_entries = await self._collect_pages(first_page)

        notes: list[FHIRDocumentReference] = []
        for entry in all_entries:
            resource = entry.get("resource", {})
            doc = parse_document_reference(resource)
            if doc is not None:
                notes.append(doc)

        # Epic stores note content as Binary resources referenced by URL.
        # Fetch text for any note that has a binary_url but no inline note_text.
        for i, note in enumerate(notes):
            if note.note_text is None and note.binary_url:
                text = await self._fetch_binary_text(note.binary_url)
                if text:
                    notes[i] = note.model_copy(update={"note_text": text})

        log.info(
            "clinical_notes_retrieved",
            encounter_id=encounter_id,
            note_count=len(notes),
        )
        return notes

    async def get_recent_labs(
        self,
        patient_id: str,
        encounter_id: str,
        loinc_codes: list[str],
        lookback_days: int = 7,
    ) -> list[FHIRObservation]:
        """
        Retrieve lab results by LOINC code within lookback window.

        Used by CDI agent for AKI, malnutrition, and sepsis trigger
        detection. Returns empty list on any FHIR error.
        """
        date_from = (
            datetime.now(timezone.utc) - timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")

        params: dict[str, str] = {
            "patient": patient_id,
            "encounter": encounter_id,
            "code": ",".join(loinc_codes),
            "date": f"ge{date_from}",
            "_sort": "-date",
        }

        raw = await self._get("/Observation", params=params)
        if isinstance(raw, DegradedResult):
            return []

        observations: list[FHIRObservation] = []
        for entry in raw.get("entry", []):
            resource = entry.get("resource", {})
            obs = parse_observation(resource)
            if obs is not None:
                observations.append(obs)

        log.info(
            "labs_retrieved",
            encounter_id=encounter_id,
            lab_count=len(observations),
            loinc_codes=loinc_codes,
        )
        return observations

    async def write_draft_claim(
        self,
        encounter_id: str,
        coding_result: Any,
        patient_id: str = "",
    ) -> dict[str, Any] | DegradedResult:
        """
        Write a draft claim to FHIR.

        Article II.1 enforcement: status is ALWAYS "draft".
        This is hardcoded — it cannot be overridden by callers.
        The active status is only set after human coder approval
        (implemented in BUILD-009 coder review UI).
        """
        claim_payload: dict[str, Any] = {
            "resourceType": "Claim",
            "status": "draft",  # Article II.1 — HARDCODED, never "active"
            "use": "claim",
            "patient": {"reference": f"Patient/{patient_id}" if patient_id else "Patient/unknown"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "created": datetime.now(timezone.utc).isoformat(),
            "diagnosis": [
                {
                    "sequence": i + 1,
                    "diagnosisCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://hl7.org/fhir/sid/icd-10-cm",
                                "code": s.code,
                                "display": s.description,
                            }
                        ]
                    },
                }
                for i, s in enumerate(coding_result.suggestions)
            ],
        }

        result = await self._post("/Claim", claim_payload)

        if isinstance(result, DegradedResult):
            return result

        log.info(
            "draft_claim_written",
            encounter_id=encounter_id,
            diagnosis_count=len(coding_result.suggestions),
            claim_status="draft",
        )
        return result

    # ─── Private HTTP methods ────────────────────────────────────────────────

    async def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | DegradedResult:
        """
        Authenticated GET with retry on transient HTTP errors.

        Non-retryable errors (400, 401, 403, 404) return DegradedResult
        immediately. Network errors (ConnectError, TimeoutException)
        also return DegradedResult immediately — they are unlikely to
        succeed on immediate retry.
        """
        url = f"{self._base_url}{path}"

        try:
            headers = await self._auth_headers()
            response = await self._http.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status not in RETRYABLE_STATUS_CODES:
                log.warning(
                    "fhir_get_non_retryable_error",
                    status_code=status,
                    path=path,
                )
                return DegradedResult(
                    error_code=_build_error_code(path, status),
                    error_message=f"HTTP {status} for {path}",
                )
            return await self._retry_get(url, params, path)

        except Exception as e:
            # Network errors: ConnectError, TimeoutException, etc.
            # Return DegradedResult immediately — no retry for connection failures.
            log.warning(
                "fhir_get_failed",
                error_type=type(e).__name__,
                path=path,
                # Never log URL params — may contain encounter/patient IDs
            )
            return DegradedResult(
                error_code=_build_error_code(path),
                error_message=f"Request failed: {type(e).__name__}",
            )

    async def _retry_get(
        self,
        url: str,
        params: dict[str, str] | None,
        path: str,
    ) -> dict[str, Any] | DegradedResult:
        """Retry loop for transient HTTP errors (429, 5xx)."""
        import asyncio

        for backoff in RETRY_BACKOFF_SECONDS:
            await asyncio.sleep(backoff)
            try:
                headers = await self._auth_headers()
                response = await self._http.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception:
                pass

        log.warning("fhir_get_retries_exhausted", path=path)
        return DegradedResult(
            error_code="FHIR_GET_RETRIES_EXHAUSTED",
            error_message=f"All retries failed for {path}",
        )

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | DegradedResult:
        """Authenticated POST with error handling."""
        url = f"{self._base_url}{path}"
        try:
            token = await self._auth.get_token()
            headers: dict[str, str] = {"Content-Type": "application/fhir+json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            response = await self._http.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            log.warning(
                "fhir_post_failed",
                error_type=type(e).__name__,
                path=path,
            )
            return DegradedResult(
                error_code="FHIR_POST_FAILED",
                error_message=f"POST failed: {type(e).__name__}",
            )

    async def _collect_pages(
        self,
        first_bundle: dict[str, Any],
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Follow FHIR Bundle pagination (link[relation=next]) and collect
        all entries across pages. Stops at max_pages to prevent runaway loops.
        Returns the combined entry list.
        """
        entries: list[dict[str, Any]] = list(first_bundle.get("entry", []))
        bundle = first_bundle
        pages_fetched = 1

        while pages_fetched < max_pages:
            next_url = next(
                (
                    link["url"]
                    for link in bundle.get("link", [])
                    if link.get("relation") == "next"
                ),
                None,
            )
            if not next_url:
                break

            # Strip base URL prefix if present — _get expects a path
            path = next_url
            if self._base_url in next_url:
                path = next_url.replace(self._base_url, "")

            result = await self._get(path)
            if isinstance(result, DegradedResult):
                log.warning("fhir_pagination_degraded", page=pages_fetched + 1)
                break

            entries.extend(result.get("entry", []))
            bundle = result
            pages_fetched += 1

        if pages_fetched > 1:
            log.info("fhir_pagination_complete", pages=pages_fetched, total_entries=len(entries))

        return entries

    async def _fetch_binary_text(self, binary_url: str) -> str:
        """
        Fetch a Binary FHIR resource and extract its text content.

        Epic stores clinical note text as a separate Binary resource
        referenced by URL from DocumentReference.content[].attachment.url.
        The URL may be relative (e.g. "Binary/abc123") or absolute.
        Returns empty string on any failure — callers skip notes with no text.
        """
        import base64

        path = binary_url if binary_url.startswith("/") else f"/{binary_url}"
        try:
            headers = await self._auth_headers()
            headers["Accept"] = "application/fhir+json, text/html, text/plain, */*"
            url = f"{self._base_url}{path}"
            response = await self._http.get(url, headers=headers)
            response.raise_for_status()

            ct = response.headers.get("content-type", "")
            if "json" in ct:
                body = response.json()
                data_b64 = body.get("data", "")
                if data_b64:
                    raw_bytes = base64.b64decode(data_b64)
                    text = raw_bytes.decode("utf-8", errors="replace").strip()
                    if "text/html" in body.get("contentType", ""):
                        import re
                        text = re.sub(r"<[^>]+>", " ", text)
                        text = re.sub(r"\s+", " ", text).strip()
                    return text
            elif "html" in ct:
                import re
                text = re.sub(r"<[^>]+>", " ", response.text)
                return re.sub(r"\s+", " ", text).strip()
            else:
                return response.text.strip()

        except Exception as e:
            log.warning(
                "binary_fetch_failed",
                binary_url=binary_url,
                error_type=type(e).__name__,
            )
            return ""

    async def _auth_headers(self) -> dict[str, str]:
        """Build authorization headers. Returns empty dict if no token."""
        token = await self._auth.get_token()
        headers = {"Accept": "application/fhir+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


# ─── Private utilities ────────────────────────────────────────────────────────


def _build_error_code(path: str, status_code: int | None = None) -> str:
    """
    Build a structured error code for DegradedResult.

    Patient-specific paths get a distinct error code so callers
    can distinguish patient-not-found from generic failures.
    """
    if "/Patient/" in path:
        return "FHIR_GET_PATIENT_FAILED"
    if status_code is not None:
        return f"FHIR_GET_{status_code}"
    return "FHIR_GET_FAILED"
