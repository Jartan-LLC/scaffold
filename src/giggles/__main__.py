"""Command-line entry point: ``python -m giggles`` or the ``giggles`` script.

Subcommands follow the phases of the plan: ``login`` and ``probe`` get you
authenticated, ``collect`` builds the dataset, ``schema`` and ``analyze`` read
it back, and ``faucets`` claims the free Aura.
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import httpx

from app.log import setup_logging
from giggles.analysis import PricingModel, classify_pricing, summarize_shapes
from giggles.auth import AuthError, password_login
from giggles.client import GigglesAPIError, GigglesClient
from giggles.collector import Collector
from giggles.config import Settings, save_tokens
from giggles.faucets import claim_all
from giggles.store import SnapshotStore

logger = logging.getLogger(__name__)


def _out(text: str) -> None:
    sys.stdout.write(text + "\n")


def _store(settings: Settings) -> SnapshotStore:
    return SnapshotStore(settings.data_dir / "snapshots.sqlite")


def cmd_login(settings: Settings, args: argparse.Namespace) -> int:
    """Log in with email/password and save the session to the data directory."""
    if not settings.supabase_anon_key:
        _out("SUPABASE_ANON_KEY is required for login (it is in the app bundle).")
        return 2
    email: str = args.email
    password = getpass.getpass("Password: ")
    with httpx.Client() as http:
        try:
            tokens = password_login(
                http, settings.supabase_url, settings.supabase_anon_key, email, password
            )
        except AuthError as exc:
            _out(f"login failed: {exc}")
            return 1
    path = save_tokens(
        settings.data_dir,
        {"access_token": tokens.access_token, "refresh_token": tokens.refresh_token},
    )
    _out(f"saved session to {path}")
    return 0


def cmd_probe(settings: Settings, _args: argparse.Namespace) -> int:
    """Hit the profile endpoint to verify auth and record the response shape."""
    with GigglesClient(settings) as client:
        try:
            profile = client.profile()
        except GigglesAPIError as exc:
            _out(f"probe failed: {exc}")
            return 1
    _out(json.dumps(profile, indent=2, default=str)[:2000])
    return 0


def cmd_collect(settings: Settings, args: argparse.Namespace) -> int:
    """Run the collector for ``--minutes``."""
    minutes: float = args.minutes
    store = _store(settings)
    with GigglesClient(settings) as client:
        Collector(client, store).run(minutes * 60.0)
    _out(f"stored {store.count()} snapshots in {settings.data_dir}")
    store.close()
    return 0


def cmd_faucets(settings: Settings, _args: argparse.Namespace) -> int:
    """Claim every faucet once and print the outcomes."""
    with GigglesClient(settings) as client:
        results = claim_all(client)
    for result in results:
        _out(f"{result.name}: {'ok' if result.ok else 'failed'} {str(result.detail)[:120]}")
    return 0 if any(r.ok for r in results) else 1


def cmd_schema(settings: Settings, _args: argparse.Namespace) -> int:
    """Summarize the response shapes recorded under ``data_dir/raw``."""
    raw_dir = settings.data_dir / "raw"
    records: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.jsonl")) if raw_dir.is_dir() else []:
        with path.open(encoding="utf-8") as fh:
            records.extend(json.loads(line) for line in fh if line.strip())
    if not records:
        _out(f"no recordings under {raw_dir}; run probe or collect first")
        return 1
    shapes = summarize_shapes(records)
    for endpoint in sorted(shapes):
        _out(endpoint)
        for key_path in sorted(shapes[endpoint]):
            _out(f"  {key_path}: {', '.join(sorted(shapes[endpoint][key_path]))}")
    return 0


def cmd_analyze(settings: Settings, args: argparse.Namespace) -> int:
    """Classify the pricing model from stored graph and trade snapshots.

    Reads the newest graph and trades snapshot per post and needs the JSON
    paths to the price points and trade timestamps, which ``schema`` reveals.
    """
    store = _store(settings)
    verdicts: dict[PricingModel, int] = dict.fromkeys(PricingModel, 0)
    for post_id in store.keys("graph"):
        graph = store.latest("graph", post_id)
        trades = store.latest("trades", post_id)
        if graph is None or trades is None:
            continue
        prices = _dig_points(graph[1], args.price_path)
        trade_times = [t for t, _ in _dig_points(trades[1], args.trade_path)]
        if not prices:
            continue
        verdict = classify_pricing(prices, trade_times)
        verdicts[verdict.model] += 1
        _out(
            f"{post_id}: {verdict.model.value} changes={verdict.changes} near_trade={verdict.changes_near_trade}"
        )
    _out("summary: " + ", ".join(f"{m.value}={n}" for m, n in verdicts.items()))
    store.close()
    return 0


def _child(node: Any, key: str) -> Any:
    if isinstance(node, dict):
        return cast("dict[str, Any]", node).get(key)
    return None


def _dig_points(payload: Any, path: str) -> list[tuple[float, float]]:
    """Extract ``(ts, value)`` pairs at a dotted path like ``data.points:t,price``."""
    dotted, _, fields = path.partition(":")
    node: Any = payload
    for part in filter(None, dotted.split(".")):
        node = _child(node, part)
        if node is None:
            return []
    if not isinstance(node, list):
        return []
    time_key, _, value_key = fields.partition(",")
    points: list[tuple[float, float]] = []
    for raw in cast("list[Any]", node):
        if not isinstance(raw, dict):
            continue
        item = cast("dict[str, Any]", raw)
        ts: Any = item.get(time_key)
        value: Any = item.get(value_key, 0.0) if value_key else 0.0
        if isinstance(ts, int | float) and isinstance(value, int | float):
            points.append((float(ts), float(value)))
    return points


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(prog="giggles", description="Headless Giggles market bot.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    parser.add_argument("--data-dir", type=Path, help="Override GIGGLES_DATA_DIR.")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Log in with email/password and save the session.")
    login.add_argument("email")
    login.set_defaults(func=cmd_login)

    sub.add_parser("probe", help="Verify auth via the profile endpoint.").set_defaults(
        func=cmd_probe
    )

    collect = sub.add_parser("collect", help="Record posts, graphs, and trades.")
    collect.add_argument("--minutes", type=float, default=60.0)
    collect.set_defaults(func=cmd_collect)

    sub.add_parser("faucets", help="Claim daily rewards, gifts, and signup trends.").set_defaults(
        func=cmd_faucets
    )
    sub.add_parser("schema", help="Summarize recorded response shapes.").set_defaults(
        func=cmd_schema
    )

    analyze = sub.add_parser("analyze", help="Classify the pricing model from stored data.")
    analyze.add_argument(
        "--price-path",
        default="points:t,price",
        help="Dotted path to the graph's point list, then ':' and the time,value keys.",
    )
    analyze.add_argument(
        "--trade-path",
        default="trades:t",
        help="Dotted path to the trade list, then ':' and the time key.",
    )
    analyze.set_defaults(func=cmd_analyze)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    settings = Settings.from_env()
    if args.data_dir is not None:
        settings = Settings.from_env({**os.environ, "GIGGLES_DATA_DIR": str(args.data_dir)})
    func: Any = args.func
    return int(func(settings, args))


if __name__ == "__main__":
    raise SystemExit(main())
