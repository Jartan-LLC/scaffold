"""Deterministic Aura income: rewards, gifts, and signup trend claims.

Each faucet is attempted independently and never raises; a failure is reported
in the result so a cron run can log it and move on. The response shapes are
unknown, so success means "the backend answered 2xx", not "Aura arrived";
compare the ledger before and after to confirm.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from giggles import endpoints
from giggles.client import GigglesAPIError, GigglesClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FaucetResult:
    """Outcome of one faucet attempt.

    Attributes:
        name: Faucet identifier.
        ok: Whether the backend answered 2xx.
        detail: Response body on success, error text on failure.
    """

    name: str
    ok: bool
    detail: Any


def claim_all(client: GigglesClient) -> list[FaucetResult]:
    """Try every known faucet once.

    Args:
        client: Authenticated client.

    Returns:
        One result per faucet, in the order attempted.
    """
    attempts: tuple[tuple[str, Callable[[], Any]], ...] = (
        ("rewards.claim", lambda: client.post(endpoints.REWARDS_CLAIM)),
        ("gift.reveal", lambda: client.post(endpoints.GIFT_REVEAL)),
        ("trends.claim_signup", lambda: client.post(endpoints.TRENDS_CLAIM_SIGNUP)),
    )
    results: list[FaucetResult] = []
    for name, call in attempts:
        try:
            body = call()
        except GigglesAPIError as exc:
            logger.info("faucet %s: HTTP %s", name, exc.status)
            results.append(FaucetResult(name, False, str(exc)))
        else:
            logger.info("faucet %s: ok", name)
            results.append(FaucetResult(name, True, body))
    return results
