"""
SMART on FHIR Backend Services authentication.
JWT assertion flow for system-to-system Epic API access.

Token lifetime is 5 minutes (Epic default) — the authenticator
proactively refreshes when <60 seconds remain.

Constitution: Article II.4 (no PHI in logs), Article III.7 (no hardcoded secrets)
Reference: docs/skills/fhir-r4-integration.md Section 5
"""
from __future__ import annotations

import time
import uuid

import structlog
from pydantic import BaseModel

log = structlog.get_logger()


class TokenCache(BaseModel):
    """Cached access token with expiry tracking."""

    access_token: str
    expires_at: float  # Unix timestamp
    token_type: str = "Bearer"

    def is_valid(self) -> bool:
        """Token is valid if more than 60 seconds remain before expiry."""
        return time.time() < (self.expires_at - 60)


class FHIRAuthenticator:
    """
    Manages SMART on FHIR Backend Services token lifecycle.

    Token flow:
    1. Generate JWT assertion signed with RS384 private key
    2. POST to Epic token endpoint
    3. Cache token until 60 seconds before expiry
    4. Auto-refresh when cache is stale

    Returns None if authentication fails — caller receives DegradedResult.
    Never raises.
    """

    def __init__(
        self,
        client_id: str,
        token_url: str,
        private_key_pem: str,
        kid: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._token_url = token_url
        self._private_key_pem = private_key_pem
        self._kid = kid
        self._cache: TokenCache | None = None

    async def get_token(self) -> str | None:
        """
        Return a valid access token. Uses cache if valid.
        Returns None if a token cannot be obtained.
        Never raises.
        """
        if self._cache and self._cache.is_valid():
            return self._cache.access_token
        return await self._fetch_new_token()

    async def _fetch_new_token(self) -> str | None:
        """Fetch a new token from the Epic token endpoint via JWT assertion."""
        try:
            import httpx
            import jwt as pyjwt

            now = int(time.time())
            payload = {
                "iss": self._client_id,
                "sub": self._client_id,
                "aud": self._token_url,
                "jti": str(uuid.uuid4()),
                "exp": now + 300,
                "iat": now,
            }

            headers = {"kid": self._kid} if self._kid else {}
            assertion = pyjwt.encode(
                payload,
                self._private_key_pem,
                algorithm="RS384",
                headers=headers,
            )

            async with httpx.AsyncClient() as http:
                response = await http.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                        "client_assertion": assertion,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                token_data = response.json()

            self._cache = TokenCache(
                access_token=token_data["access_token"],
                expires_at=time.time() + token_data.get("expires_in", 300),
            )

            log.info(
                "fhir_token_obtained",
                expires_in_seconds=token_data.get("expires_in", 300),
            )
            return self._cache.access_token

        except Exception as e:
            log.warning(
                "fhir_token_fetch_failed",
                error_type=type(e).__name__,
                # Never log private_key_pem, client_id, or any credential
            )
            return None
