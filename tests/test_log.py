"""Tests for the logging setup."""

import json
import logging

from app.log import JsonFormatter, PlainFormatter, setup_logging


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
