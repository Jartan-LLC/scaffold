"""HTTP client for the Giggles backend.

Adds what the app's own network layer has and a bot needs on top of ``httpx``:
bearer auth with one automatic refresh on 401, a minimum spacing between
requests, retry with backoff on 429 and 5xx, and a recorder that appends every
exchange to a JSONL file so response shapes can be learned offline.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from giggles import endpoints
from giggles.auth import AuthError, Tokens, refresh_session
from giggles.config import Settings, save_tokens

logger = logging.getLogger(__name__)

Json = Any
"""A decoded JSON body. Shapes are unknown until the recorder has seen them."""

REQUEST_TIMEOUT_S = 20.0
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
RETRY_STATUSES = frozenset({429, 502, 503, 504})
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 1.0
RECORD_TEXT_LIMIT = 4000


class GigglesAPIError(RuntimeError):
    """A non-retryable error response from the backend.

    Attributes:
        status: HTTP status code.
        body: Decoded JSON body, or the raw text when it was not JSON.
    """

    def __init__(self, status: int, body: Json) -> None:
        """Store the failing status and body.

        Args:
            status: HTTP status code.
            body: Decoded response body.
        """
        super().__init__(f"HTTP {status}: {str(body)[:200]}")
        self.status = status
        self.body = body


class Recorder:
    """Append every request/response pair to a dated JSONL file.

    Args:
        directory: Folder for ``raw/YYYY-MM-DD.jsonl`` files; created on first write.
    """

    def __init__(self, directory: Path) -> None:
        """Remember the target directory; nothing is created until the first record."""
        self.directory = directory

    def record(self, entry: Mapping[str, Any]) -> None:
        """Write one JSON line.

        Args:
            entry: Fields to persist; must be JSON-serializable.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        day = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        with (self.directory / f"{day}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")


def _decode(response: httpx.Response) -> Json:
    try:
        return response.json()
    except ValueError:
        return response.text[:RECORD_TEXT_LIMIT]


class GigglesClient:
    """Authenticated, rate-limited, recording client.

    Args:
        settings: Connection settings and initial tokens.
        transport: Optional ``httpx`` transport (tests pass a ``MockTransport``).
        recorder: Where exchanges are logged; defaults to ``data_dir/raw``.
        sleep: Sleep function, injectable so tests do not wait.
        clock: Monotonic clock, injectable for the same reason.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        recorder: Recorder | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Set up the underlying ``httpx`` client and pacing state."""
        self.settings = settings
        self.tokens = (
            Tokens(settings.access_token, settings.refresh_token) if settings.access_token else None
        )
        self.recorder = recorder or Recorder(settings.data_dir / "raw")
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        self._http = httpx.Client(
            base_url=settings.base_url,
            transport=transport,
            timeout=REQUEST_TIMEOUT_S,
            headers={"Accept": "application/json", "User-Agent": settings.user_agent},
        )

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._http.close()

    def __enter__(self) -> GigglesClient:
        """Support ``with GigglesClient(...) as client``."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close on context exit."""
        self.close()

    # --- plumbing ------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        if self.tokens is None:
            return {}
        return {"Authorization": f"Bearer {self.tokens.access_token}"}

    def _pace(self) -> None:
        if self._last_request_at is not None:
            wait = self.settings.min_interval_s - (self._clock() - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = self._clock()

    def _refresh(self) -> bool:
        if self.tokens is None or not self.tokens.refresh_token:
            return False
        if not self.settings.supabase_anon_key:
            logger.warning("401 received but SUPABASE_ANON_KEY is unset; cannot refresh")
            return False
        try:
            self.tokens = refresh_session(
                self._http,
                self.settings.supabase_url,
                self.settings.supabase_anon_key,
                self.tokens.refresh_token,
            )
        except AuthError:
            logger.exception("token refresh failed")
            return False
        save_tokens(
            self.settings.data_dir,
            {"access_token": self.tokens.access_token, "refresh_token": self.tokens.refresh_token},
        )
        return True

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Json:
        """Send one request with pacing, retry, refresh, and recording.

        Args:
            method: HTTP method.
            path: Path relative to the base URL.
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            The decoded response body.

        Raises:
            GigglesAPIError: On a 4xx/5xx that retry and refresh could not clear.
        """
        refreshed = False
        for attempt in range(MAX_ATTEMPTS):
            self._pace()
            started = self._clock()
            response = self._http.request(
                method, path, params=params, json=json_body, headers=self._auth_headers()
            )
            body = _decode(response)
            self.recorder.record(
                {
                    "ts": datetime.now(tz=UTC).isoformat(),
                    "method": method,
                    "path": path,
                    "params": dict(params) if params else None,
                    "request": dict(json_body) if json_body else None,
                    "status": response.status_code,
                    "elapsed_ms": round((self._clock() - started) * 1000),
                    "body": body,
                }
            )
            if response.status_code < HTTP_BAD_REQUEST:
                return body
            if response.status_code == HTTP_UNAUTHORIZED and not refreshed:
                refreshed = True
                if self._refresh():
                    continue
            if response.status_code in RETRY_STATUSES and attempt < MAX_ATTEMPTS - 1:
                delay = BACKOFF_BASE_S * (2**attempt)
                logger.info("HTTP %s on %s; retrying in %.0fs", response.status_code, path, delay)
                self._sleep(delay)
                continue
            raise GigglesAPIError(response.status_code, body)
        raise AssertionError("unreachable: loop always returns or raises")

    def get(self, path: str, **params: Any) -> Json:
        """GET ``path`` with ``params`` as the query string."""
        return self.request("GET", path, params=params or None)

    def post(self, path: str, json_body: Mapping[str, Any] | None = None) -> Json:
        """POST ``json_body`` to ``path``."""
        return self.request("POST", path, json_body=json_body)

    # --- discovery -----------------------------------------------------------

    def feed(self, *, cursor: str | None = None, limit: int = 20) -> Json:
        """Fetch a page of the main feed."""
        return self.get(endpoints.FEED, cursor=cursor, limit=limit)

    def random_videos(self, count: int = 20) -> Json:
        """Fetch ``count`` random posts, the cheapest wide sample of the catalog."""
        return self.get(endpoints.FEED_RANDOM, count=count)

    def most_increased(self, limit: int = 50) -> Json:
        """Fetch the explore board of posts whose value rose most."""
        return self.get(endpoints.MOST_INCREASED, limit=limit)

    def post_detail(self, post_id: str) -> Json:
        """Fetch one post with its engagement counters."""
        return self.get(endpoints.POST.format(post_id=post_id))

    # --- market --------------------------------------------------------------

    def market_graph(self, post_id: str, **params: Any) -> Json:
        """Fetch a post's price series (``period``/``timeframe`` are accepted upstream)."""
        return self.get(endpoints.POST_MARKET_GRAPH.format(post_id=post_id), **params)

    def market_trades(self, post_id: str, **params: Any) -> Json:
        """Fetch a post's trade tape."""
        return self.get(endpoints.POST_MARKET_TRADES.format(post_id=post_id), **params)

    def invest(self, post_id: str, payload: Mapping[str, Any]) -> Json:
        """Submit a buy or sell on ``post_id``.

        The body schema is not in the bundle dump beyond the field names
        ``shares``, ``points``, and ``position``; confirm it from a recorded
        trade made in the app before relying on this.

        Args:
            post_id: Post to trade.
            payload: Request body exactly as the app sends it.

        Returns:
            The decoded response body.
        """
        return self.post(endpoints.POST_INVEST.format(post_id=post_id), payload)

    # --- portfolio -----------------------------------------------------------

    def portfolio(self) -> Json:
        """Fetch open positions."""
        return self.get(endpoints.PORTFOLIO)

    def closed_positions(self, **params: Any) -> Json:
        """Fetch settled or sold positions."""
        return self.get(endpoints.CLOSED_POSITIONS, **params)

    def transactions(self, **params: Any) -> Json:
        """Fetch the Aura ledger."""
        return self.get(endpoints.TRANSACTIONS, **params)

    def leaderboard(self, **params: Any) -> Json:
        """Fetch the trader leaderboard."""
        return self.get(endpoints.LEADERBOARD, **params)

    def user_portfolio(self, user_id: str) -> Json:
        """Fetch another user's public portfolio."""
        return self.get(endpoints.USER_PORTFOLIO.format(user_id=user_id))

    def profile(self) -> Json:
        """Fetch the signed-in user's profile; the cheapest auth check."""
        return self.get(endpoints.PROFILE)
