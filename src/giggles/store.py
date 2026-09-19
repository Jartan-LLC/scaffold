"""SQLite snapshot store.

Rows are ``(ts, kind, key, body)`` with the body kept as raw JSON text. That is
deliberate: the response schemas are unknown until Phase 0 has run, and a
typed schema now would only be rewritten. Analysis code reads the JSON back
and extracts what it needs.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id   INTEGER PRIMARY KEY,
    ts   REAL NOT NULL,
    kind TEXT NOT NULL,
    key  TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS snapshots_kind_key_ts ON snapshots (kind, key, ts);
"""


class SnapshotStore:
    """Append-only store of JSON snapshots keyed by kind and key.

    Args:
        path: SQLite file, or ``":memory:"``.

    Example:
        >>> store = SnapshotStore(":memory:")
        >>> store.put("post", "42", {"views": 10}, ts=1.0)
        >>> store.put("post", "42", {"views": 25}, ts=2.0)
        >>> [(ts, body["views"]) for ts, body in store.series("post", "42")]
        [(1.0, 10), (2.0, 25)]
        >>> store.keys("post")
        ['42']
    """

    def __init__(self, path: str | Path) -> None:
        """Open (and create if needed) the database at ``path``."""
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def put(self, kind: str, key: str, body: Any, *, ts: float | None = None) -> None:
        """Append one snapshot.

        Args:
            kind: Category, such as ``"post"`` or ``"graph"``.
            key: Identifier within the kind, usually a post id.
            body: JSON-serializable payload.
            ts: Unix time; defaults to now.
        """
        stamp = time.time() if ts is None else ts
        self._conn.execute(
            "INSERT INTO snapshots (ts, kind, key, body) VALUES (?, ?, ?, ?)",
            (stamp, kind, key, json.dumps(body, default=str)),
        )
        self._conn.commit()

    def series(self, kind: str, key: str) -> list[tuple[float, Any]]:
        """Return every snapshot for ``(kind, key)`` in time order.

        Args:
            kind: Category to read.
            key: Identifier within the kind.

        Returns:
            ``(ts, body)`` pairs, oldest first.
        """
        rows = self._conn.execute(
            "SELECT ts, body FROM snapshots WHERE kind = ? AND key = ? ORDER BY ts",
            (kind, key),
        ).fetchall()
        return [(float(ts), json.loads(body)) for ts, body in rows]

    def latest(self, kind: str, key: str) -> tuple[float, Any] | None:
        """Return the newest snapshot for ``(kind, key)``, or ``None``."""
        row = self._conn.execute(
            "SELECT ts, body FROM snapshots WHERE kind = ? AND key = ? ORDER BY ts DESC LIMIT 1",
            (kind, key),
        ).fetchone()
        if row is None:
            return None
        return float(row[0]), json.loads(row[1])

    def keys(self, kind: str) -> list[str]:
        """Return the distinct keys seen for ``kind``, sorted."""
        rows = self._conn.execute(
            "SELECT DISTINCT key FROM snapshots WHERE kind = ? ORDER BY key", (kind,)
        ).fetchall()
        return [str(row[0]) for row in rows]

    def count(self, kind: str | None = None) -> int:
        """Count snapshots, optionally restricted to one kind."""
        if kind is None:
            row = self._conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM snapshots WHERE kind = ?", (kind,)
            ).fetchone()
        return int(row[0]) if row else 0
