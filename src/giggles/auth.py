"""Supabase auth: password login and refresh-token exchange.

These are the same public GoTrue endpoints the app calls, authenticated with the
project's anon key from the bundle. The backend then accepts the resulting JWT
as ``Authorization: Bearer``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

REQUEST_TIMEOUT_S = 20.0
HTTP_BAD_REQUEST = 400


class AuthError(RuntimeError):
    """Raised when Supabase rejects a login or refresh."""


@dataclass(frozen=True)
class Tokens:
    """A Supabase session.

    Attributes:
        access_token: JWT presented to the backend.
        refresh_token: Opaque token exchanged for a new session.
        expires_at: Unix time the access token stops working, or ``None`` if unknown.
    """

    access_token: str
    refresh_token: str | None
    expires_at: float | None = None

    def expires_within(self, seconds: float, *, now: float | None = None) -> bool:
        """Report whether the access token expires within ``seconds`` from ``now``.

        Args:
            seconds: Look-ahead window.
            now: Unix time to compare against; defaults to the current time.

        Returns:
            ``True`` when expiry is unknown or falls inside the window.

        Example:
            >>> Tokens("a", "r", expires_at=1000).expires_within(60, now=950)
            True
            >>> Tokens("a", "r", expires_at=1000).expires_within(30, now=950)
            False
        """
        if self.expires_at is None:
            return True
        current = time.time() if now is None else now
        return self.expires_at - current <= seconds


def _session_from_response(payload: dict[str, Any]) -> Tokens:
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise AuthError("auth response has no access_token")
    refresh = payload.get("refresh_token")
    expires_at = payload.get("expires_at")
    if expires_at is None and isinstance(payload.get("expires_in"), int | float):
        expires_at = time.time() + float(payload["expires_in"])
    return Tokens(
        access_token=access,
        refresh_token=refresh if isinstance(refresh, str) else None,
        expires_at=float(expires_at) if isinstance(expires_at, int | float) else None,
    )


def _token_request(
    http: httpx.Client, supabase_url: str, anon_key: str, grant: str, body: dict[str, str]
) -> Tokens:
    response = http.post(
        f"{supabase_url}/auth/v1/token",
        params={"grant_type": grant},
        json=body,
        headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    if response.status_code >= HTTP_BAD_REQUEST:
        raise AuthError(f"{grant} failed: HTTP {response.status_code}: {response.text[:200]}")
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise AuthError("auth response is not a JSON object")
    return _session_from_response(payload)  # pyright: ignore[reportUnknownArgumentType]


def password_login(
    http: httpx.Client, supabase_url: str, anon_key: str, email: str, password: str
) -> Tokens:
    """Exchange an email and password for a session.

    Args:
        http: Client to send with (tests inject a mock transport).
        supabase_url: Supabase project origin.
        anon_key: Public anon key.
        email: Account email.
        password: Account password.

    Returns:
        The new session tokens.

    Raises:
        AuthError: When Supabase rejects the credentials or answers unexpectedly.
    """
    body = {"email": email, "password": password}
    return _token_request(http, supabase_url, anon_key, "password", body)


def refresh_session(
    http: httpx.Client, supabase_url: str, anon_key: str, refresh_token: str
) -> Tokens:
    """Exchange a refresh token for a fresh session.

    Args:
        http: Client to send with.
        supabase_url: Supabase project origin.
        anon_key: Public anon key.
        refresh_token: The current refresh token.

    Returns:
        The new session tokens.

    Raises:
        AuthError: When the refresh token is rejected.
    """
    body = {"refresh_token": refresh_token}
    return _token_request(http, supabase_url, anon_key, "refresh_token", body)
