"""Decision math shared by every strategy: edge, sizing, and copy-trade diffs.

Pure functions only. The model that produces ``p`` and ``b`` lives elsewhere;
this module makes sure a prediction never turns into a trade that the fee or
the exit liquidity would eat.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


def net_edge(expected_gross_return: float, round_trip_cost: float) -> float:
    """Expected return after paying the round trip.

    Args:
        expected_gross_return: Predicted price change as a fraction, e.g. ``0.12``.
        round_trip_cost: Measured fee plus spread as a fraction, e.g. ``0.05``.

    Returns:
        ``(1 + gross) * (1 - cost) - 1``.

    Example:
        >>> round(net_edge(0.12, 0.05), 4)
        0.064
    """
    return (1.0 + expected_gross_return) * (1.0 - round_trip_cost) - 1.0


def kelly_fraction(p: float, b: float, *, fraction: float = 0.25) -> float:
    """Fractional Kelly stake as a share of bankroll.

    Args:
        p: Probability the position wins.
        b: Net odds: profit per unit staked when it wins (loss is the full stake).
        fraction: Multiplier on full Kelly; ``0.25`` is a conservative default.

    Returns:
        Stake fraction in ``[0, 1]``; ``0.0`` when the edge is non-positive.

    Example:
        >>> round(kelly_fraction(0.6, 1.0, fraction=1.0), 3)
        0.2
        >>> kelly_fraction(0.4, 1.0)
        0.0
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be a probability")
    if b <= 0:
        return 0.0
    full = p - (1.0 - p) / b
    return max(0.0, min(1.0, full * fraction))


def position_size(
    bankroll: float,
    stake_fraction: float,
    *,
    recent_volume: float,
    max_volume_share: float = 0.1,
    max_position: float | None = None,
) -> float:
    """Cap a Kelly stake by what the post's market can absorb.

    Args:
        bankroll: Aura available.
        stake_fraction: Output of :func:`kelly_fraction`.
        recent_volume: Aura traded on the post over the lookback window.
        max_volume_share: Largest share of that volume one position may be.
        max_position: Absolute cap in Aura, if any.

    Returns:
        Aura to stake.

    Example:
        >>> position_size(1000, 0.2, recent_volume=500)
        50.0
        >>> position_size(1000, 0.02, recent_volume=500)
        20.0
    """
    size = bankroll * stake_fraction
    size = min(size, recent_volume * max_volume_share)
    if max_position is not None:
        size = min(size, max_position)
    return max(0.0, size)


class SignalKind(StrEnum):
    """What a followed portfolio did between two snapshots."""

    ENTER = "enter"
    ADD = "add"
    REDUCE = "reduce"
    EXIT = "exit"


@dataclass(frozen=True)
class CopySignal:
    """One change in a followed portfolio.

    Attributes:
        post_id: Post whose position changed.
        kind: Direction of the change.
        before: Aura held before.
        after: Aura held after.
    """

    post_id: str
    kind: SignalKind
    before: float
    after: float


def portfolio_diff(before: Mapping[str, float], after: Mapping[str, float]) -> list[CopySignal]:
    """Diff two portfolio snapshots into copy-trade signals.

    Args:
        before: ``{post_id: aura_held}`` at the earlier snapshot.
        after: Same at the later snapshot.

    Returns:
        Signals sorted by post id.

    Example:
        >>> [s.kind.value for s in portfolio_diff({"a": 10, "b": 5}, {"a": 20, "c": 3})]
        ['add', 'exit', 'enter']
    """
    signals: list[CopySignal] = []
    for post_id in sorted(before.keys() | after.keys()):
        old = before.get(post_id, 0.0)
        new = after.get(post_id, 0.0)
        if old == new:
            continue
        if old == 0:
            kind = SignalKind.ENTER
        elif new == 0:
            kind = SignalKind.EXIT
        elif new > old:
            kind = SignalKind.ADD
        else:
            kind = SignalKind.REDUCE
        signals.append(CopySignal(post_id, kind, old, new))
    return signals
