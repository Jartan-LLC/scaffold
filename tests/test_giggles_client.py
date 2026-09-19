"""Tests for the backend client: auth header, pacing, retry, refresh, recording."""

import json
from pathlib import Path

import httpx
import pytest

from giggles.client import GigglesAPIError, GigglesClient, Recorder
from giggles.config import Settings

pytestmark = pytest.mark.unit


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _client(
    handler: httpx.MockTransport, tmp_path: Path, clock: FakeClock, **overrides: object
) -> GigglesClient:
    fields: dict[str, object] = {
        "access_token": "tok",
        "refresh_token": "ref",
        "supabase_anon_key": "anon",
        "data_dir": tmp_path,
        "min_interval_s": 1.0,
        **overrides,
    }
    settings = Settings(**fields)  # pyright: ignore[reportArgumentType]
    return GigglesClient(settings, transport=handler, sleep=clock.sleep, clock=clock)


def test_sends_bearer_and_records(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": 1})

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), tmp_path, clock)
    assert client.profile() == {"id": 1}
    assert seen[0].headers["Authorization"] == "Bearer tok"
    assert seen[0].headers["Accept"] == "application/json"
    lines = list((tmp_path / "raw").glob("*.jsonl"))
    assert len(lines) == 1
    record = json.loads(lines[0].read_text().splitlines()[0])
    assert record["path"] == "/api/user/profile"
    assert record["status"] == 200
    assert record["body"] == {"id": 1}


def test_paces_requests(tmp_path: Path) -> None:
    handler = httpx.MockTransport(lambda _req: httpx.Response(200, json=[]))
    clock = FakeClock()
    client = _client(handler, tmp_path, clock)
    client.feed()
    client.feed()
    assert clock.slept == [1.0]  # second call waited out the minimum interval


def test_retries_on_429_then_succeeds(tmp_path: Path) -> None:
    calls = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429) if calls == 1 else httpx.Response(200, json={"ok": True})

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), tmp_path, clock)
    assert client.feed() == {"ok": True}
    assert calls == 2
    assert 1.0 in clock.slept  # backoff before the retry


def test_gives_up_after_max_attempts(tmp_path: Path) -> None:
    handler = httpx.MockTransport(lambda _req: httpx.Response(503, text="down"))
    client = _client(handler, tmp_path, FakeClock())
    with pytest.raises(GigglesAPIError) as excinfo:
        client.feed()
    assert excinfo.value.status == 503


def test_refreshes_once_on_401(tmp_path: Path) -> None:
    auths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/token":
            assert request.url.params["grant_type"] == "refresh_token"
            assert request.headers["apikey"] == "anon"
            return httpx.Response(200, json={"access_token": "new", "refresh_token": "ref2"})
        auths.append(request.headers["Authorization"])
        return httpx.Response(401) if auths[-1] == "Bearer tok" else httpx.Response(200, json={})

    client = _client(httpx.MockTransport(handler), tmp_path, FakeClock())
    assert client.profile() == {}
    assert auths == ["Bearer tok", "Bearer new"]
    saved = json.loads((tmp_path / "tokens.json").read_text())
    assert saved == {"access_token": "new", "refresh_token": "ref2"}


def test_401_without_refresh_token_raises(tmp_path: Path) -> None:
    handler = httpx.MockTransport(lambda _req: httpx.Response(401, json={"error": "expired"}))
    client = _client(handler, tmp_path, FakeClock(), refresh_token=None)
    with pytest.raises(GigglesAPIError) as excinfo:
        client.profile()
    assert excinfo.value.status == 401


def test_non_json_body_is_recorded_as_text(tmp_path: Path) -> None:
    handler = httpx.MockTransport(lambda _req: httpx.Response(200, text="<html>"))
    client = _client(handler, tmp_path, FakeClock())
    assert client.feed() == "<html>"


def test_recorder_appends_one_line_per_entry(tmp_path: Path) -> None:
    recorder = Recorder(tmp_path / "raw")
    recorder.record({"a": 1})
    recorder.record({"b": Path("x")})  # non-JSON values fall back to str()
    text = next((tmp_path / "raw").glob("*.jsonl")).read_text()
    assert [json.loads(line) for line in text.splitlines()] == [{"a": 1}, {"b": "x"}]
