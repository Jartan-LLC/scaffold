"""Tests for the collector loop, the store, faucets, and the CLI wiring."""

import json
from pathlib import Path

import httpx
import pytest

from giggles.__main__ import main
from giggles.client import GigglesClient
from giggles.collector import Collector, cadence_for, extract_post_ids
from giggles.config import Settings
from giggles.faucets import claim_all
from giggles.store import SnapshotStore

pytestmark = pytest.mark.unit


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _backend(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/v3/feed":
        return httpx.Response(
            200, json={"posts": [{"id": "p1", "views": 3}, {"id": "p2", "caption": "x"}]}
        )
    if path == "/api/videos/random":
        return httpx.Response(200, json=[{"id": "p1", "views": 9}])
    if path == "/api/v3/explore/most-increased":
        return httpx.Response(200, json={"data": [{"id": "gone", "views": 1}]})
    if path == "/api/v2/posts/gone":
        return httpx.Response(404, json={"error": "not found"})
    if path.startswith("/api/v2/posts/"):
        return httpx.Response(200, json={"id": path.rsplit("/", 1)[-1], "views": 42})
    if path.endswith("/market/graph"):
        return httpx.Response(200, json={"points": [{"t": 1, "price": 1.0}]})
    if path.endswith("/market/trades"):
        return httpx.Response(200, json={"trades": [{"t": 1}]})
    if path == "/api/v3/rewards/claim":
        return httpx.Response(200, json={"aura": 50})
    if path.startswith(("/api/v3/gift", "/api/v3/trends")):
        return httpx.Response(400, json={"error": "nothing to claim"})
    return httpx.Response(200, json={"me": True})


def _client(tmp_path: Path, clock: FakeClock) -> GigglesClient:
    settings = Settings(access_token="tok", data_dir=tmp_path, min_interval_s=0.0)
    return GigglesClient(
        settings, transport=httpx.MockTransport(_backend), sleep=clock.sleep, clock=clock
    )


def test_extract_post_ids_needs_a_post_like_key() -> None:
    payload = {"items": [{"id": 1, "views": 2}, {"id": 2}, {"nested": {"id": "u", "caption": ""}}]}
    assert extract_post_ids(payload) == ["1", "u"]


def test_cadence_decays_with_age() -> None:
    assert cadence_for(0) < cadence_for(4000) < cadence_for(100_000)


def test_tick_discovers_polls_and_drops_404(tmp_path: Path) -> None:
    clock = FakeClock()
    store = SnapshotStore(":memory:")
    collector = Collector(_client(tmp_path, clock), store, clock=clock, sleep=clock.sleep)
    polled = collector.tick()
    assert polled == 3  # p1, p2, gone
    assert set(collector.watched) == {"p1", "p2"}  # "gone" was 404 and dropped
    assert store.count("post") == 2
    assert store.count("graph") == 2
    assert store.count("trades") == 2
    assert store.count("discovery") == 3
    assert store.count("leaderboard") == 1
    # nothing is due until the cadence elapses
    assert collector.tick() == 0
    clock.now += cadence_for(0)
    assert collector.tick() == 2


def test_run_sleeps_when_idle(tmp_path: Path) -> None:
    clock = FakeClock()
    collector = Collector(
        _client(tmp_path, clock), SnapshotStore(":memory:"), clock=clock, sleep=clock.sleep
    )
    collector.run(20.0, idle_s=5.0)
    assert clock.slept  # idle ticks slept instead of spinning


def test_store_latest_and_missing(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "db" / "s.sqlite")
    assert store.latest("post", "x") is None
    store.put("post", "x", {"v": 1}, ts=1.0)
    store.put("post", "x", {"v": 2}, ts=2.0)
    assert store.latest("post", "x") == (2.0, {"v": 2})
    assert store.count() == 2
    store.close()


def test_claim_all_reports_each_faucet(tmp_path: Path) -> None:
    results = claim_all(_client(tmp_path, FakeClock()))
    by_name = {r.name: r.ok for r in results}
    assert by_name == {"rewards.claim": True, "gift.reveal": False, "trends.claim_signup": False}


def test_cli_schema_reports_missing_recordings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--data-dir", str(tmp_path), "schema"]) == 1
    assert "no recordings" in capsys.readouterr().out


def test_cli_schema_summarizes_recordings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "d.jsonl").write_text(
        json.dumps({"method": "GET", "path": "/api/v2/posts/9", "body": {"views": 1}}) + "\n"
    )
    assert main(["--data-dir", str(tmp_path), "schema"]) == 0
    out = capsys.readouterr().out
    assert "GET /api/v2/posts/{id}" in out
    assert "views: int" in out


def test_cli_analyze_reads_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = SnapshotStore(tmp_path / "snapshots.sqlite")
    trades = [10.0, 30.0, 50.0, 70.0, 90.0]
    points = [{"t": 0, "price": 1.0}]
    price = 1.0
    for t in trades:
        points.append({"t": t - 1, "price": price})
        price *= 1.1
        points.append({"t": t + 0.5, "price": price})
    store.put("graph", "p", {"points": points})
    store.put("trades", "p", {"trades": [{"t": t} for t in trades]})
    store.close()
    assert main(["--data-dir", str(tmp_path), "analyze"]) == 0
    out = capsys.readouterr().out
    assert "p: bonding_curve" in out
    assert "bonding_curve=1" in out
