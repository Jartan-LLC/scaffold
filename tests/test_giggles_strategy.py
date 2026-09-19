"""Tests for edge, sizing, and copy-trade diff math."""

import pytest

from giggles.strategy import SignalKind, kelly_fraction, net_edge, portfolio_diff, position_size

pytestmark = pytest.mark.unit


def test_net_edge_negative_when_fee_eats_return() -> None:
    assert net_edge(0.03, 0.05) < 0


def test_kelly_zero_for_no_edge_or_bad_odds() -> None:
    assert kelly_fraction(0.5, 1.0) == 0.0
    assert kelly_fraction(0.9, 0.0) == 0.0


def test_kelly_scales_with_fraction_and_clamps() -> None:
    assert kelly_fraction(0.6, 1.0, fraction=0.5) == pytest.approx(0.1)
    assert kelly_fraction(1.0, 1.0, fraction=5.0) == 1.0


def test_kelly_rejects_bad_probability() -> None:
    with pytest.raises(ValueError, match="probability"):
        kelly_fraction(1.5, 1.0)


def test_position_size_respects_every_cap() -> None:
    assert position_size(1000, 0.5, recent_volume=10_000) == 500.0
    assert position_size(1000, 0.5, recent_volume=100) == 10.0
    assert position_size(1000, 0.5, recent_volume=10_000, max_position=75) == 75.0
    assert position_size(1000, 0.0, recent_volume=10_000) == 0.0


def test_portfolio_diff_classifies_every_transition() -> None:
    before = {"enter": 0, "add": 10, "reduce": 10, "exit": 10, "same": 5}
    after = {"enter": 4, "add": 20, "reduce": 5, "exit": 0, "same": 5}
    kinds = {s.post_id: s.kind for s in portfolio_diff(before, after)}
    assert kinds == {
        "enter": SignalKind.ENTER,
        "add": SignalKind.ADD,
        "reduce": SignalKind.REDUCE,
        "exit": SignalKind.EXIT,
    }
