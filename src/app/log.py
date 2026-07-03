"""Logging setup — plain text or single-line JSON, with control-char escaping.

Escaping neutralizes terminal-escape and log-forging sequences that can arrive
in messages built from untrusted input — on both the message and the exception
traceback. Call :func:`setup_logging` once at startup; get named loggers
elsewhere with ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import json
import logging
import logging.config
from datetime import UTC, datetime
from types import TracebackType
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

# Same, but keep LF so multi-line tracebacks stay readable — only embedded
# control chars (e.g. an ESC smuggled into an exception message) are escaped.
_EXC_ESCAPES = str.maketrans(
    {
        **{c: f"\\x{c:02x}" for c in range(0x20) if c not in (_TAB, 0x0A, 0x0D)},
        0x0D: "\\r",
        0x7F: "\\x7f",
        **{c: f"\\x{c:02x}" for c in range(0x80, 0xA0)},
    }
)

# The tuple shape of sys.exc_info(), which logging.Formatter.formatException
# receives — spelled out to avoid importing the private logging._SysExcInfoType.
_SysExcInfo = (
    tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
)


class PlainFormatter(logging.Formatter):
    """Human-readable formatter that escapes control characters.

    Neutralizes control chars in the message and traceback; a traceback's own
    newlines are preserved for readability.
    """

    def __init__(self) -> None:
        """Format records as ``<timestamp> <level> <logger> <message>``."""
        super().__init__(fmt="%(asctime)s %(levelname)s %(name)s %(message)s")

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802 (stdlib override)
        """Render the message, escaping every control character (newlines included).

        Args:
            record: The log record being formatted.

        Returns:
            The rendered message with control characters escaped.
        """
        return super().formatMessage(record).translate(_CONTROL_ESCAPES)

    def formatException(self, ei: _SysExcInfo) -> str:  # noqa: N802 (stdlib override)
        """Render an exception, escaping control chars but keeping its newlines.

        Args:
            ei: The ``sys.exc_info()``-style tuple to format.

        Returns:
            The formatted traceback with embedded control characters escaped and
            its own line breaks preserved.
        """
        return super().formatException(ei).translate(_EXC_ESCAPES)

    def formatStack(self, stack_info: str) -> str:  # noqa: N802 (stdlib override)
        """Render stack info, escaping control chars but keeping its newlines.

        Args:
            stack_info: The stack-trace string to format.

        Returns:
            The formatted stack info with control characters escaped.
        """
        return super().formatStack(stack_info).translate(_EXC_ESCAPES)


class JsonFormatter(logging.Formatter):
    """One line of JSON per record, for log aggregators.

    ``json.dumps`` escapes control chars in the JSON it emits, but a consumer
    that *decodes* a field (e.g. ``jq -r '.exc'`` to a terminal) undoes that —
    so the message and the traceback are escaped here too, keeping decoded
    values injection-safe.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record to a single line of JSON.

        Args:
            record: The log record being formatted.

        Returns:
            A one-line JSON object with timestamp, level, logger, message, and
            (when the record carries one) the exception text.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage().translate(_CONTROL_ESCAPES),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info).translate(_EXC_ESCAPES)
        return json.dumps(payload, default=str)


def setup_logging(*, level: int = logging.INFO, fmt: str = "plain") -> None:
    """Configure the root logger once, at application startup.

    Args:
        level: Root log level, e.g. ``logging.INFO``.
        fmt: ``"plain"`` for human-readable text or ``"json"`` for aggregators.

    Example:
        >>> setup_logging(level=logging.DEBUG, fmt="json")
        >>> logging.getLogger(__name__).info("ready")
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
