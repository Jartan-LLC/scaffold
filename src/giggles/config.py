"""Runtime settings, read from the environment and an optional token file.

Nothing here is secret by default: the backend and Supabase URLs ship in the
app bundle. The bearer and refresh tokens are the credentials, and they live in
``GIGGLES_ACCESS_TOKEN`` / ``GIGGLES_REFRESH_TOKEN`` or in ``tokens.json`` under
the data directory, which ``giggles login`` writes.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_BASE_URL = "https://giggles-backend-production.up.railway.app"
DEFAULT_SUPABASE_URL = "https://dwxhmelcardeplqxxdsc.supabase.co"
DEFAULT_DATA_DIR = "giggles-data"
DEFAULT_MIN_INTERVAL_S = 1.5
DEFAULT_USER_AGENT = "okhttp/4.12.0"  # the React Native Android client's default stack

TOKEN_FILE = "tokens.json"  # noqa: S105 (a filename, not a secret)


@dataclass(frozen=True)
class Settings:
    """Everything the client and collector need to run.

    Attributes:
        base_url: Backend origin, without a trailing slash.
        supabase_url: Supabase project origin used for auth.
        supabase_anon_key: Public anon key from the bundle; needed for login/refresh.
        access_token: Bearer token sent to the backend.
        refresh_token: Supabase refresh token used when the access token expires.
        data_dir: Where raw logs, the SQLite store, and tokens are kept.
        min_interval_s: Minimum spacing between requests, to look like one person.
        user_agent: ``User-Agent`` header value.
    """

    base_url: str = DEFAULT_BASE_URL
    supabase_url: str = DEFAULT_SUPABASE_URL
    supabase_anon_key: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    data_dir: Path = Path(DEFAULT_DATA_DIR)
    min_interval_s: float = DEFAULT_MIN_INTERVAL_S
    user_agent: str = DEFAULT_USER_AGENT

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from environment variables, falling back to the token file.

        Args:
            env: Mapping to read instead of ``os.environ`` (tests pass a dict).

        Returns:
            Settings with any tokens found in the environment or ``tokens.json``.

        Example:
            >>> s = Settings.from_env({"GIGGLES_ACCESS_TOKEN": "abc", "GIGGLES_DATA_DIR": "/tmp/x"})
            >>> s.access_token, s.data_dir.name
            ('abc', 'x')
        """
        src = os.environ if env is None else env
        settings = cls(
            base_url=src.get("GIGGLES_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            supabase_url=src.get("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/"),
            supabase_anon_key=src.get("SUPABASE_ANON_KEY") or None,
            access_token=src.get("GIGGLES_ACCESS_TOKEN") or None,
            refresh_token=src.get("GIGGLES_REFRESH_TOKEN") or None,
            data_dir=Path(src.get("GIGGLES_DATA_DIR", DEFAULT_DATA_DIR)),
            min_interval_s=float(src.get("GIGGLES_MIN_INTERVAL_S", DEFAULT_MIN_INTERVAL_S)),
            user_agent=src.get("GIGGLES_USER_AGENT", DEFAULT_USER_AGENT),
        )
        if settings.access_token is None:
            saved = load_tokens(settings.data_dir)
            if saved:
                settings = replace(
                    settings,
                    access_token=saved.get("access_token"),
                    refresh_token=saved.get("refresh_token") or settings.refresh_token,
                )
        return settings


def load_tokens(data_dir: Path) -> dict[str, str]:
    """Read ``tokens.json`` from the data directory.

    Args:
        data_dir: Directory that may contain the token file.

    Returns:
        The stored string fields, or an empty dict when the file is absent or malformed.
    """
    path = data_dir / TOKEN_FILE
    if not path.is_file():
        return {}
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if isinstance(v, str)}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def save_tokens(data_dir: Path, tokens: Mapping[str, str | None]) -> Path:
    """Write tokens to ``tokens.json`` with owner-only permissions.

    Args:
        data_dir: Directory to write into; created if missing.
        tokens: Fields to persist; ``None`` values are dropped.

    Returns:
        The path written.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / TOKEN_FILE
    payload = {k: v for k, v in tokens.items() if v is not None}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    path.chmod(0o600)
    return path
