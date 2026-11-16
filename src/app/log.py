r"""Logging setup — plain text or single-line JSON, with unsafe characters escaped.

Escaping neutralizes terminal-escape and log-forging sequences that can arrive
in messages built from untrusted input — on both the message and the exception
traceback. The unsafe characters are the control characters but tab, the Unicode
line and paragraph separators, and the invisible format characters, such as
bidirectional controls and zero-width characters. Each is written as its Python
escape: ``\x1b``, ``\u2028``, ``\u202e``. Call :func:`setup_logging` once at
startup; get named loggers elsewhere with ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import json
import logging
import logging.config
import time
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Literal

# The unsafe characters, by Unicode category: Cc (controls), Zl and Zp (line and
# paragraph separators, where str.splitlines() and other Unicode-aware readers break
# lines) and Cf (format characters: invisible, and able to change how neighbouring text
# displays). All of Cf, U+200D (zero-width joiner) included: emoji sequences that use it
# show as escapes, but outside one it hides in text as U+200B does. Listed as of Unicode
# 16.0, because deriving the list from unicodedata at import scans every code point; the
# tests check it against the running Python's database.
_TAB = 0x09  # the one C0 control we keep literal
_UNSAFE_RANGES = (
    (0x0000, 0x001F),  # C0 controls
    (0x007F, 0x009F),  # DEL, C1 controls
    (0x00AD, 0x00AD),
    (0x0600, 0x0605),
    (0x061C, 0x061C),
    (0x06DD, 0x06DD),
    (0x070F, 0x070F),
    (0x0890, 0x0891),
    (0x08E2, 0x08E2),
    (0x180E, 0x180E),
    (0x200B, 0x200F),
    (0x2028, 0x202E),
    (0x2060, 0x2064),
    (0x2066, 0x206F),
    (0xFEFF, 0xFEFF),
    (0xFFF9, 0xFFFB),
    (0x110BD, 0x110BD),
    (0x110CD, 0x110CD),
    (0x13430, 0x1343F),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0001, 0xE0001),
    (0xE0020, 0xE007F),
)


def _escapes(*, keep: frozenset[int]) -> dict[int, str]:
    return str.maketrans(
        {
            c: chr(c).encode("unicode_escape").decode("ascii")
            for first, last in _UNSAFE_RANGES
            for c in range(first, last + 1)
            if c not in keep
        }
    )


_ESCAPES = _escapes(keep=frozenset({_TAB}))
# Same, but keep LF so multi-line tracebacks stay readable — only embedded
# unsafe chars (e.g. an ESC smuggled into an exception message) are escaped.
_EXC_ESCAPES = _escapes(keep=frozenset({_TAB, 0x0A}))

# The tuple shape of sys.exc_info(), which logging.Formatter.formatException
# receives — spelled out to avoid importing the private logging._SysExcInfoType.
_SysExcInfo = (
    tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
)


class PlainFormatter(logging.Formatter):
    """Human-readable formatter that escapes unsafe characters.

    Escapes them in the message and traceback; a traceback's own newlines are
    preserved for readability.
    """

    # Timestamps in UTC (stdlib default is local time) so plain and JSON agree.
    converter = staticmethod(time.gmtime)

    def __init__(self) -> None:
        """Format records as ``<timestamp> <level> <logger> <message>``."""
        super().__init__(fmt="%(asctime)s %(levelname)s %(name)s %(message)s")

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802 (stdlib override)
        """Render the message, escaping every unsafe character (newlines included).

        Args:
            record: The log record being formatted.

        Returns:
            The rendered message with unsafe characters escaped.
        """
        return super().formatMessage(record).translate(_ESCAPES)

    def formatException(self, ei: _SysExcInfo) -> str:  # noqa: N802 (stdlib override)
        """Render an exception, escaping unsafe characters but keeping its newlines.

        Args:
            ei: The ``sys.exc_info()``-style tuple to format.

        Returns:
            The formatted traceback with embedded unsafe characters escaped and
            its own line breaks preserved.
        """
        return super().formatException(ei).translate(_EXC_ESCAPES)

    def formatStack(self, stack_info: str) -> str:  # noqa: N802 (stdlib override)
        """Render stack info, escaping unsafe characters but keeping its newlines.

        Args:
            stack_info: The stack-trace string to format.

        Returns:
            The formatted stack info with unsafe characters escaped.
        """
        return super().formatStack(stack_info).translate(_EXC_ESCAPES)


class JsonFormatter(logging.Formatter):
    """One line of JSON per record, for log aggregators.

    ``json.dumps`` escapes non-ASCII characters and most controls in the JSON it
    emits, but a consumer that *decodes* a field (e.g. ``jq -r '.logger'`` to a
    terminal) undoes that — so every string field (logger name included, since it
    can be built from untrusted input) is escaped here too, keeping decoded values
    injection-safe.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record to a single line of JSON.

        Args:
            record: The log record being formatted.

        Returns:
            A one-line JSON object with timestamp, level, logger, message, and —
            when the record carries them — the exception text and stack info.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.translate(_ESCAPES),
            "logger": record.name.translate(_ESCAPES),
            "message": record.getMessage().translate(_ESCAPES),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info).translate(_EXC_ESCAPES)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info).translate(_EXC_ESCAPES)
        return json.dumps(payload, default=str)


def setup_logging(*, level: int = logging.INFO, fmt: Literal["plain", "json"] = "plain") -> None:
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
