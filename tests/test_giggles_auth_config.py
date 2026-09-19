"""Tests for Supabase auth calls and settings loading."""

import json
from pathlib import Path

import httpx
import pytest

from giggles.auth import AuthError, Tokens, password_login, refresh_session
from giggles.config import Settings, load_tokens, save_tokens

pytestmark = pytest.mark.unit


def test_password_login_posts_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "password"
        assert request.headers["apikey"] == "anon"
        assert json.loads(request.content) == {"email": "a@b.c", "password": "pw"}
        return httpx.Response(
            200, json={"access_token": "acc", "refresh_token": "ref", "expires_in": 3600}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        tokens = password_login(http, "https://sb.example", "anon", "a@b.c", "pw")
    assert tokens.access_token == "acc"
    assert tokens.refresh_token == "ref"
    assert tokens.expires_at is not None


def test_refresh_session_rejected_raises() -> None:
    handler = httpx.MockTransport(lambda _r: httpx.Response(400, json={"error": "invalid"}))
    with (
        httpx.Client(transport=handler) as http,
        pytest.raises(AuthError, match="refresh_token failed"),
    ):
        refresh_session(http, "https://sb.example", "anon", "stale")


def test_missing_access_token_raises() -> None:
    handler = httpx.MockTransport(lambda _r: httpx.Response(200, json={"user": {}}))
    with httpx.Client(transport=handler) as http, pytest.raises(AuthError, match="access_token"):
        password_login(http, "https://sb.example", "anon", "a@b.c", "pw")


def test_tokens_expiry_window() -> None:
    assert Tokens("a", None).expires_within(1)  # unknown expiry is treated as due
    assert not Tokens("a", None, expires_at=100.0).expires_within(10, now=50.0)


def test_settings_reads_token_file_when_env_lacks_token(tmp_path: Path) -> None:
    save_tokens(tmp_path, {"access_token": "file-tok", "refresh_token": "file-ref"})
    settings = Settings.from_env({"GIGGLES_DATA_DIR": str(tmp_path)})
    assert settings.access_token == "file-tok"
    assert settings.refresh_token == "file-ref"


def test_env_token_wins_over_file(tmp_path: Path) -> None:
    save_tokens(tmp_path, {"access_token": "file-tok"})
    settings = Settings.from_env(
        {"GIGGLES_DATA_DIR": str(tmp_path), "GIGGLES_ACCESS_TOKEN": "env-tok"}
    )
    assert settings.access_token == "env-tok"


def test_load_tokens_tolerates_garbage(tmp_path: Path) -> None:
    (tmp_path / "tokens.json").write_text("not json")
    assert load_tokens(tmp_path) == {}
    (tmp_path / "tokens.json").write_text("[1, 2]")
    assert load_tokens(tmp_path) == {}


def test_save_tokens_drops_none_and_restricts_mode(tmp_path: Path) -> None:
    path = save_tokens(tmp_path / "nested", {"access_token": "a", "refresh_token": None})
    assert json.loads(path.read_text()) == {"access_token": "a"}
    assert path.stat().st_mode & 0o777 == 0o600
