"""Phase 0 analysis: identify the pricing model and measure the frictions.

Everything here is a pure function over plain sequences so it can run on data
extracted from :class:`giggles.store.SnapshotStore` or on synthetic fixtures.
"""

from __future__ import annotations

import bisect
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from typing import Any

BONDING_CURVE_MIN_FRACTION = 0.9
ENGAGEMENT_MAX_FRACTION = 0.3
WINDOWED_MIN_ALIGNMENT = 0.8
MIN_CHANGES_FOR_VERDICT = 5


class PricingModel(StrEnum):
    """Hypotheses for how a post's price is set."""

    BONDING_CURVE = "bonding_curve"
    """Price moves only when someone trades."""

    ENGAGEMENT_INDEXED = "engagement_indexed"
    """Price moves with views/likes regardless of trades."""

    HYBRID = "hybrid"
    """Both trades and engagement move the price."""

    UNKNOWN = "unknown"
    """Too few price changes to say."""


@dataclass(frozen=True)
class PricingVerdict:
    """Result of :func:`classify_pricing`.

    Attributes:
        model: The best-fitting hypothesis.
        changes: Number of price changes observed.
        changes_near_trade: How many of those coincided with a trade.
        fraction: ``changes_near_trade / changes`` (``0.0`` when no changes).
    """

    model: PricingModel
    changes: int
    changes_near_trade: int
    fraction: float


def classify_pricing(
    prices: Sequence[tuple[float, float]],
    trade_times: Sequence[float],
    *,
    tolerance_s: float = 2.0,
) -> PricingVerdict:
    """Decide whether price changes coincide with trades.

    Args:
        prices: ``(ts, price)`` points in time order.
        trade_times: Unix times of trades on the same post.
        tolerance_s: How close a trade must be to a price change to count.

    Returns:
        The verdict with its supporting counts.

    Example:
        >>> trades = [10, 30, 50, 70, 90]
        >>> steps = [(0, 1.0)] + [(t + 0.5, 1.0 + 0.1 * n) for n, t in enumerate(trades, 1)]
        >>> classify_pricing(steps, trades).model
        <PricingModel.BONDING_CURVE: 'bonding_curve'>
        >>> drift = [(t, 1.0 + 0.01 * t) for t in range(0, 100, 5)]
        >>> classify_pricing(drift, [40]).model
        <PricingModel.ENGAGEMENT_INDEXED: 'engagement_indexed'>
    """
    sorted_trades = sorted(trade_times)
    changes = 0
    near = 0
    for (_, prev), (ts, cur) in pairwise(prices):
        if math.isclose(prev, cur, rel_tol=1e-9, abs_tol=1e-12):
            continue
        changes += 1
        if _has_trade_near(sorted_trades, ts, tolerance_s):
            near += 1
    fraction = near / changes if changes else 0.0
    if changes < MIN_CHANGES_FOR_VERDICT:
        model = PricingModel.UNKNOWN
    elif fraction >= BONDING_CURVE_MIN_FRACTION:
        model = PricingModel.BONDING_CURVE
    elif fraction <= ENGAGEMENT_MAX_FRACTION:
        model = PricingModel.ENGAGEMENT_INDEXED
    else:
        model = PricingModel.HYBRID
    return PricingVerdict(model, changes, near, fraction)


def _has_trade_near(sorted_trades: Sequence[float], ts: float, tolerance_s: float) -> bool:
    idx = bisect.bisect_left(sorted_trades, ts - tolerance_s)
    return idx < len(sorted_trades) and sorted_trades[idx] <= ts + tolerance_s


def settlement_alignment(
    close_times: Sequence[float], *, period_s: float, tolerance_s: float = 120.0
) -> float:
    """Measure how many position closes sit on a fixed period boundary.

    A high value means positions settle on a schedule (the windowed model in the
    research doc) rather than whenever users sell.

    Args:
        close_times: Unix times at which positions closed.
        period_s: Candidate window length, such as ``3600`` or ``86400``.
        tolerance_s: Slack around each boundary.

    Returns:
        Fraction of closes within ``tolerance_s`` of a multiple of ``period_s``,
        or ``0.0`` when there are no closes.

    Example:
        >>> round(settlement_alignment([3600, 7200 + 30, 5000], period_s=3600), 3)
        0.667
    """
    if not close_times:
        return 0.0
    aligned = 0
    for ts in close_times:
        offset = ts % period_s
        if min(offset, period_s - offset) <= tolerance_s:
            aligned += 1
    return aligned / len(close_times)


def round_trip_cost(spent: float, received: float) -> float:
    """Fraction of Aura lost on an immediate buy-then-sell.

    Args:
        spent: Aura paid on the buy.
        received: Aura returned on the sell.

    Returns:
        ``1 - received / spent``; the fee plus spread plus any curve slippage.

    Example:
        >>> round(round_trip_cost(100, 94), 3)
        0.06
    """
    if spent <= 0:
        raise ValueError("spent must be positive")
    return 1.0 - received / spent


@dataclass(frozen=True)
class VelocityFeatures:
    """Shape of an engagement or price series over its recent history.

    Attributes:
        last: Latest value.
        delta: Change over the last interval.
        rate_per_min: Change per minute over the last interval.
        acceleration: Difference between the last two rates, per minute squared.
        log_growth: ``log1p(last) - log1p(first)`` across the whole series.
    """

    last: float
    delta: float
    rate_per_min: float
    acceleration: float
    log_growth: float


def velocity_features(series: Sequence[tuple[float, float]]) -> VelocityFeatures:
    """Compute early-velocity features from ``(ts, value)`` points.

    Args:
        series: At least one ``(ts, value)`` point in time order.

    Returns:
        The features; rates are ``0.0`` when there are too few points.

    Example:
        >>> f = velocity_features([(0, 0), (60, 100), (120, 300)])
        >>> f.last, f.delta, f.rate_per_min, f.acceleration
        (300.0, 200.0, 200.0, 100.0)
    """
    if not series:
        raise ValueError("series must not be empty")
    values = [float(v) for _, v in series]
    times = [float(t) for t, _ in series]
    rates = [
        (values[i] - values[i - 1]) / max((times[i] - times[i - 1]) / 60.0, 1e-9)
        for i in range(1, len(values))
    ]
    delta = values[-1] - values[-2] if len(values) > 1 else 0.0
    rate = rates[-1] if rates else 0.0
    accel = rates[-1] - rates[-2] if len(rates) > 1 else 0.0
    log_growth = math.log1p(max(values[-1], 0.0)) - math.log1p(max(values[0], 0.0))
    return VelocityFeatures(values[-1], delta, rate, accel, log_growth)


_ID_SEGMENT = re.compile(r"^(\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")


def template_path(path: str) -> str:
    """Replace numeric and UUID path segments with ``{id}``.

    Example:
        >>> template_path("/api/posts/12345/market/graph")
        '/api/posts/{id}/market/graph'
    """
    return "/".join("{id}" if _ID_SEGMENT.match(seg) else seg for seg in path.split("/"))


def summarize_shapes(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, set[str]]]:
    """Summarize the JSON key paths and value types seen per endpoint.

    Feed it the JSONL lines the client's recorder wrote and it returns, for each
    ``METHOD /templated/path``, every key path and the type names observed
    there. This is how Phase 0 turns raw traffic into a schema.

    Args:
        records: Recorder entries with ``method``, ``path``, and ``body``.

    Returns:
        ``{endpoint: {key_path: {type_name, ...}}}``.

    Example:
        >>> recs = [{"method": "GET", "path": "/api/posts/1", "body": {"id": 1, "tags": ["a"]}}]
        >>> summarize_shapes(recs)["GET /api/posts/{id}"] == {"id": {"int"}, "tags": {"list"}, "tags[]": {"str"}}
        True
    """
    shapes: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for rec in records:
        endpoint = f"{rec.get('method', '?')} {template_path(str(rec.get('path', '')))}"
        for key_path, type_name in _leaf_types(rec.get("body"), ""):
            shapes[endpoint][key_path].add(type_name)
    return {k: dict(v) for k, v in shapes.items()}


def _leaf_types(node: Any, prefix: str) -> Iterable[tuple[str, str]]:
    if isinstance(node, dict):
        if prefix:
            yield prefix, "dict"
        for key, value in node.items():  # pyright: ignore[reportUnknownVariableType]
            child = f"{prefix}.{key}" if prefix else str(key)  # pyright: ignore[reportUnknownArgumentType]
            yield from _leaf_types(value, child)
    elif isinstance(node, list):
        yield prefix, "list"
        for value in node:  # pyright: ignore[reportUnknownVariableType]
            yield from _leaf_types(value, f"{prefix}[]")
    else:
        yield prefix, type(node).__name__
