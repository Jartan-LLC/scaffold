"""Tests for the logging setup."""

import json
import logging
import sys
from collections.abc import Iterator

import pytest

from app.log import JsonFormatter, PlainFormatter, setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]  # invoked by pytest
    root = logging.getLogger()
    level, handlers = root.level, root.handlers[:]
    yield
    root.setLevel(level)
    root.handlers[:] = handlers


def _record(msg: str, name: str = "app.test") -> logging.LogRecord:
    return logging.LogRecord(name, logging.INFO, __file__, 1, msg, None, None)


def test_plain_formatter_escapes_control_chars() -> None:
    out = PlainFormatter().format(_record("hi\x1b[31mred\x00"))
    assert "\x1b" not in out
    assert "\\x1b" in out
    assert "\x00" not in out


def test_json_formatter_is_single_line_json() -> None:
    out = JsonFormatter().format(_record("hello"))
    assert "\n" not in out
    payload = json.loads(out)
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"


def test_json_formatter_escapes_control_chars() -> None:
    payload = json.loads(JsonFormatter().format(_record("x\x1by")))
    assert "\x1b" not in payload["message"]
    assert "\\x1b" in payload["message"]


def test_setup_logging_plain_configures_root() -> None:
    setup_logging(level=logging.DEBUG, fmt="plain")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert root.handlers


def test_setup_logging_json_uses_json_formatter() -> None:
    setup_logging(fmt="json")
    formatter = logging.getLogger().handlers[0].formatter
    assert isinstance(formatter, JsonFormatter)


def test_plain_formatter_escapes_exception_text() -> None:
    try:
        raise ValueError("boom\x1b[2Jevil")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "op failed", None, exc_info)
    out = PlainFormatter().format(record)
    assert "\x1b" not in out  # ESC in the exception message is escaped
    assert "\\x1b" in out
    assert "\n" in out  # multi-line traceback stays readable


def test_plain_formatter_escapes_stack_info() -> None:
    record = _record("op")
    record.stack_info = "Stack (most recent call last):\n  frame\x1b[2Jhidden"
    out = PlainFormatter().format(record)
    assert "\x1b" not in out  # ESC smuggled into stack info is escaped
    assert "\\x1b" in out
    assert "\n" in out  # stack newlines stay readable


def test_json_formatter_escapes_exception_text() -> None:
    try:
        raise ValueError("boom\x1bevil")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "op failed", None, exc_info)
    payload = json.loads(JsonFormatter().format(record))
    assert "\x1b" not in payload["exc"]  # decoded exc field is injection-safe
    assert "\\x1b" in payload["exc"]
