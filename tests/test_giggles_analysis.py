"""Tests for the pricing-model classifier and its companions."""

import pytest

from giggles.analysis import (
    PricingModel,
    classify_pricing,
    round_trip_cost,
    settlement_alignment,
    summarize_shapes,
    template_path,
    velocity_features,
)

pytestmark = pytest.mark.unit


def _steps(trade_times: list[float]) -> list[tuple[float, float]]:
    """A price series that only moves at (and just after) each trade."""
    points: list[tuple[float, float]] = [(0.0, 1.0)]
    price = 1.0
    for t in trade_times:
        points.append((t - 1.0, price))
        price *= 1.1
        points.append((t + 0.5, price))
    return points


def test_bonding_curve_when_changes_follow_trades() -> None:
    trades = [10.0, 30.0, 50.0, 70.0, 90.0, 110.0]
    verdict = classify_pricing(_steps(trades), trades)
    assert verdict.model is PricingModel.BONDING_CURVE
    assert verdict.changes == len(trades)
    assert verdict.changes_near_trade == len(trades)


def test_engagement_indexed_when_price_drifts_without_trades() -> None:
    drift = [(float(t), 1.0 + 0.01 * t) for t in range(0, 300, 5)]
    verdict = classify_pricing(drift, [150.0])
    assert verdict.model is PricingModel.ENGAGEMENT_INDEXED
    assert verdict.fraction < 0.1


def test_hybrid_in_between() -> None:
    trades = [10.0, 30.0, 50.0]
    series = [*_steps(trades), (200.0, 2.0), (210.0, 2.1), (220.0, 2.2)]
    verdict = classify_pricing(series, trades)
    assert verdict.model is PricingModel.HYBRID


def test_unknown_with_too_few_changes() -> None:
    verdict = classify_pricing([(0.0, 1.0), (1.0, 1.0), (2.0, 1.1)], [2.0])
    assert verdict.model is PricingModel.UNKNOWN


def test_settlement_alignment_detects_hourly_closes() -> None:
    hourly = [3600.0 * k + 10 for k in range(1, 11)]
    assert settlement_alignment(hourly, period_s=3600) == 1.0
    scattered = [3600.0 * k + 1700 for k in range(1, 11)]
    assert settlement_alignment(scattered, period_s=3600) == 0.0
    assert settlement_alignment([], period_s=3600) == 0.0


def test_round_trip_cost_rejects_zero_spend() -> None:
    with pytest.raises(ValueError, match="positive"):
        round_trip_cost(0, 1)


def test_velocity_features_single_point() -> None:
    f = velocity_features([(0.0, 5.0)])
    assert (f.last, f.delta, f.rate_per_min, f.acceleration, f.log_growth) == (5.0, 0, 0, 0, 0)


def test_velocity_features_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        velocity_features([])


def test_template_path_handles_uuid_and_ints() -> None:
    assert template_path("/api/v2/users/3f2504e0-4f89-11d3-9a0c-0305e82c3301/portfolio") == (
        "/api/v2/users/{id}/portfolio"
    )
    assert template_path("/api/v3/feed") == "/api/v3/feed"


def test_summarize_shapes_merges_types_across_records() -> None:
    records = [
        {"method": "GET", "path": "/api/posts/1", "body": {"views": 1, "meta": {"x": None}}},
        {"method": "GET", "path": "/api/posts/2", "body": {"views": 2.5, "meta": {"x": "s"}}},
    ]
    shapes = summarize_shapes(records)
    assert set(shapes) == {"GET /api/posts/{id}"}
    assert shapes["GET /api/posts/{id}"]["views"] == {"int", "float"}
    assert shapes["GET /api/posts/{id}"]["meta.x"] == {"NoneType", "str"}
    assert shapes["GET /api/posts/{id}"]["meta"] == {"dict"}
