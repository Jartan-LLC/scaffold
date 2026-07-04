"""Tests for the logging setup."""

import json
import logging
import os
import sys
import time
from collections.abc import Iterator

import pytest

from app.log import JsonFormatter, PlainFormatter, setup_logging

pytestmark = pytest.mark.unit


@pytest.fixture
def _non_utc_tz() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]  # invoked by pytest
    """Force a non-UTC local zone so the UTC-timestamp assertions actually bite."""
    if not hasattr(time, "tzset"):  # tzset is Unix-only
        pytest.skip("time.tzset() unavailable on this platform")
    original = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    yield
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def _record(msg: str, name: str = "app.test") -> logging.LogRecord:
    return logging.LogRecord(name, logging.INFO, __file__, 1, msg, None, None)


def test_plain_formatter_escapes_control_chars() -> None:
    out = PlainFormatter().format(_record("hi\x1b[31mred\x00"))
    assert "\x1b" not in out
    assert "\\x1b" in out
    assert "\x00" not in out
    assert "\\x00" in out  # escaped, not merely dropped


def test_plain_formatter_escapes_message_newline() -> None:
    out = PlainFormatter().format(_record("line1\nline2"))
    assert "\n" not in out  # a message newline can't forge a new log line
    assert "line1\\nline2" in out


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


def test_json_formatter_escapes_logger_name() -> None:
    payload = json.loads(JsonFormatter().format(_record("hi", name="worker\x1bevil")))
    assert "\x1b" not in payload["logger"]  # dynamic logger names can carry input
    assert "\\x1b" in payload["logger"]


def test_json_formatter_escapes_message_newline() -> None:
    payload = json.loads(JsonFormatter().format(_record("line1\nline2")))
    assert "\n" not in payload["message"]  # decoded message can't forge a log line
    assert payload["message"] == "line1\\nline2"


@pytest.mark.usefixtures("_non_utc_tz")
def test_json_formatter_uses_utc_timestamps() -> None:
    record = _record("hi")
    record.created = 1609459200.0  # 2021-01-01T00:00:00Z
    payload = json.loads(JsonFormatter().format(record))
    assert payload["timestamp"].startswith("2021-01-01T00:00:00")  # UTC, not host local time


def test_setup_logging_plain_configures_root() -> None:
    setup_logging(level=logging.DEBUG, fmt="plain")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert root.handlers
    assert isinstance(root.handlers[0].formatter, PlainFormatter)


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


def test_json_formatter_emits_escaped_stack_info() -> None:
    record = _record("op")
    record.stack_info = "Stack (most recent call last):\n  frame\x1b[2Jhidden"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["stack"]  # stack is present, not silently dropped
    assert "\x1b" not in payload["stack"]  # decoded stack field is injection-safe
    assert "\\x1b" in payload["stack"]


@pytest.mark.usefixtures("_non_utc_tz")
def test_plain_formatter_uses_utc_timestamps() -> None:
    record = _record("hi")
    record.created = 1609459200.0  # 2021-01-01T00:00:00Z
    out = PlainFormatter().format(record)
    assert out.startswith("2021-01-01 00:00:00")  # UTC, not the host's local time
