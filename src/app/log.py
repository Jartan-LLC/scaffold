"""Logging setup — plain text or single-line JSON, with control-char escaping.

Escaping neutralizes terminal-escape and log-forging sequences that can arrive
in messages built from untrusted input. Call :func:`setup_logging` once at
startup; get named loggers elsewhere with ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

# Escape C0 control chars (except tab), CR/LF, DEL, and C1 controls — any of
# which can drive terminal escape sequences or forge new log lines.
_TAB = 0x09  # the one C0 control we keep literal

_CONTROL_ESCAPES = str.maketrans(
    {
        **{c: f"\\x{c:02x}" for c in range(0x20) if c != _TAB},
        0x0A: "\\n",
        0x0D: "\\r",
        0x7F: "\\x7f",
        **{c: f"\\x{c:02x}" for c in range(0x80, 0xA0)},
    }
)


class PlainFormatter(logging.Formatter):
    """Human-readable formatter that escapes control chars in the message."""

    def __init__(self) -> None:
        """Use a ``timestamp level logger message`` layout."""
        super().__init__(fmt="%(asctime)s %(levelname)s %(name)s %(message)s")

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802 (stdlib override)
        """Render the record, escaping control chars in the message body."""
        return super().formatMessage(record).translate(_CONTROL_ESCAPES)


class JsonFormatter(logging.Formatter):
    """Single-line JSON formatter for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record to one line of JSON."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage().translate(_CONTROL_ESCAPES),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(*, level: int = logging.INFO, fmt: str = "plain") -> None:
    """Configure stdlib logging once at startup.

    Args:
        level: Root log level, e.g. ``logging.INFO``.
        fmt: ``"plain"`` for readable text or ``"json"`` for aggregators.
    """
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain": {"()": PlainFormatter},
                "json": {"()": JsonFormatter},
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": fmt,
                },
            },
            "root": {"level": level, "handlers": ["stderr"]},
        }
    )
