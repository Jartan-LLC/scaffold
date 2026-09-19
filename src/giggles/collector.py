"""Phase 0 data collection: discover posts, then snapshot each one on a decaying cadence.

A post is polled every minute for its first hour, then every five minutes, then
every half hour. Each poll stores the post detail (engagement counters), its
price graph, and its trade tape. Once an hour the collector also stores the
leaderboard, the most-increased board, and the caller's own portfolio and
ledger, which the fee and settlement analyses need.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from giggles.client import GigglesAPIError, GigglesClient
from giggles.store import SnapshotStore

logger = logging.getLogger(__name__)

POST_HINT_KEYS = frozenset(
    {"video_url", "thumbnail_url", "caption", "views", "view_count", "creator", "user_id", "likes"}
)
"""Keys whose presence next to an ``id`` marks a dict as a post."""

CADENCE: tuple[tuple[float, float], ...] = (
    (3600.0, 60.0),
    (6 * 3600.0, 300.0),
    (float("inf"), 1800.0),
)
"""``(max_age_s, interval_s)`` pairs, first match wins."""

GLOBAL_INTERVAL_S = 3600.0
MAX_WATCHED = 300


def cadence_for(age_s: float) -> float:
    """Return the polling interval for a post of the given age.

    Args:
        age_s: Seconds since the post was first seen.

    Returns:
        Seconds to wait between polls.

    Example:
        >>> cadence_for(0), cadence_for(3599), cadence_for(3600), cadence_for(10**6)
        (60.0, 60.0, 300.0, 1800.0)
    """
    for max_age, interval in CADENCE:
        if age_s < max_age:
            return interval
    return CADENCE[-1][1]


def extract_post_ids(payload: Any) -> list[str]:
    """Find post ids anywhere in a response, without knowing its layout.

    Walks the JSON tree and collects the ``id`` of every dict that also carries a
    post-like key from :data:`POST_HINT_KEYS`. Order of first appearance is kept
    and duplicates dropped.

    Args:
        payload: Decoded JSON.

    Returns:
        Post ids as strings.

    Example:
        >>> extract_post_ids({"data": [{"id": 7, "views": 3}, {"id": 8, "name": "not a post"}]})
        ['7']
    """
    found: list[str] = []
    seen: set[str] = set()
    for node in _walk(payload):
        if "id" in node and POST_HINT_KEYS & node.keys():
            ident = str(node["id"])
            if ident not in seen:
                seen.add(ident)
                found.append(ident)
    return found


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node  # pyright: ignore[reportUnknownVariableType]
        for value in node.values():  # pyright: ignore[reportUnknownVariableType]
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:  # pyright: ignore[reportUnknownVariableType]
            yield from _walk(value)


@dataclass
class Watch:
    """Polling state for one post.

    Attributes:
        first_seen: Unix time the collector first saw the post.
        next_due: Unix time of the next poll.
    """

    first_seen: float
    next_due: float


@dataclass
class Collector:
    """Discovery and polling loop over the video market.

    ``clock`` (Unix-time source) and ``sleep`` are injectable so tests can drive
    the loop without waiting.

    Attributes:
        client: Backend client.
        store: Destination for snapshots.
        watched: Posts under observation, by id.
    """

    client: GigglesClient
    store: SnapshotStore
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    watched: dict[str, Watch] = field(default_factory=dict[str, Watch])
    _next_global: float = 0.0

    def discover(self) -> int:
        """Pull the discovery surfaces and start watching any new posts.

        Returns:
            Number of posts newly added to the watch set.
        """
        sources: tuple[tuple[str, Callable[[], Any]], ...] = (
            ("feed", self.client.feed),
            ("random", self.client.random_videos),
            ("most_increased", self.client.most_increased),
        )
        added = 0
        now = self.clock()
        for name, fetch in sources:
            try:
                payload = fetch()
            except GigglesAPIError:
                logger.exception("discovery source %s failed", name)
                continue
            self.store.put("discovery", name, payload, ts=now)
            for post_id in extract_post_ids(payload):
                if post_id not in self.watched and len(self.watched) < MAX_WATCHED:
                    self.watched[post_id] = Watch(first_seen=now, next_due=now)
                    added += 1
        return added

    def poll_post(self, post_id: str) -> None:
        """Snapshot one post's detail, graph, and trades.

        Args:
            post_id: Post to poll.
        """
        now = self.clock()
        for kind, fetch in (
            ("post", self.client.post_detail),
            ("graph", self.client.market_graph),
            ("trades", self.client.market_trades),
        ):
            try:
                self.store.put(kind, post_id, fetch(post_id), ts=now)
            except GigglesAPIError as exc:
                logger.warning("%s %s failed: %s", kind, post_id, exc)
                if exc.status == 404:  # noqa: PLR2004 (HTTP status)
                    self.watched.pop(post_id, None)
                    return

    def poll_global(self) -> None:
        """Snapshot the account-level and market-wide surfaces."""
        now = self.clock()
        for kind, fetch in (
            ("leaderboard", self.client.leaderboard),
            ("portfolio", self.client.portfolio),
            ("closed_positions", self.client.closed_positions),
            ("transactions", self.client.transactions),
        ):
            try:
                self.store.put(kind, "me", fetch(), ts=now)
            except GigglesAPIError as exc:
                logger.warning("%s failed: %s", kind, exc)

    def tick(self) -> int:
        """Run everything that is due right now.

        Returns:
            Number of posts polled.
        """
        now = self.clock()
        if now >= self._next_global:
            self.discover()
            self.poll_global()
            self._next_global = now + GLOBAL_INTERVAL_S
        polled = 0
        for post_id, watch in list(self.watched.items()):
            if watch.next_due <= now:
                self.poll_post(post_id)
                polled += 1
                if post_id in self.watched:
                    watch.next_due = now + cadence_for(now - watch.first_seen)
        return polled

    def run(self, duration_s: float, *, idle_s: float = 5.0) -> None:
        """Loop :meth:`tick` for ``duration_s`` seconds.

        Args:
            duration_s: How long to run.
            idle_s: Sleep between ticks when nothing was due.
        """
        deadline = self.clock() + duration_s
        while self.clock() < deadline:
            polled = self.tick()
            logger.info(
                "tick: polled=%d watched=%d rows=%d", polled, len(self.watched), self.store.count()
            )
            if polled == 0:
                self.sleep(idle_s)
