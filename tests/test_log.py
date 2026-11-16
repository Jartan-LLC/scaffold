"""Tests for the logging setup."""

import json
import logging
import os
import sys
import time
import unicodedata
from collections.abc import Iterator

import pytest
from hypothesis import given
from hypothesis import strategies as st

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


# The escaping guarantee, stated against the running Python's Unicode database rather than
# app.log's own table: every control character except tab, line and paragraph separators,
# and format characters.
_UNSAFE_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")


def _is_unsafe(char: str) -> bool:
    return char != "\t" and unicodedata.category(char) in _UNSAFE_CATEGORIES


def _unsafe_in(text: str, *, allow: str = "") -> set[str]:
    return {c for c in text if _is_unsafe(c) and c not in allow}


_UNSAFE = "".join(filter(_is_unsafe, map(chr, range(sys.maxunicode + 1))))

# Unsafe characters join the text as segments of their own: drawn as part of st.text()'s
# alphabet, they would come almost only from the low code points, the C0 controls.
_texts = st.lists(st.text() | st.sampled_from(_UNSAFE)).map("".join)
_safe_texts = st.text(
    st.characters(codec="utf-8", exclude_categories=_UNSAFE_CATEGORIES) | st.just("\t")
)


def _error_record(text: str) -> logging.LogRecord:
    try:
        raise ValueError(text)
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "op failed", None, exc_info)
    record.stack_info = f"Stack (most recent call last):\n  {text}"
    return record


@given(name=_texts, message=_texts)
def test_plain_record_is_one_line_of_safe_characters(name: str, message: str) -> None:
    out = PlainFormatter().format(_record(message, name=name))
    assert len(out.splitlines()) == 1
    assert not _unsafe_in(out)


@given(name=_texts, message=_texts)
def test_json_record_is_one_line_with_safe_decoded_fields(name: str, message: str) -> None:
    out = JsonFormatter().format(_record(message, name=name))
    assert len(out.splitlines()) == 1
    payload = json.loads(out)
    for field in ("level", "logger", "message"):
        assert not _unsafe_in(payload[field])


@given(text=_texts)
def test_tracebacks_keep_only_their_own_newlines(text: str) -> None:
    plain = PlainFormatter().format(_error_record(text))
    assert not _unsafe_in(plain, allow="\n")
    payload = json.loads(JsonFormatter().format(_error_record(text)))
    assert not _unsafe_in(payload["exc"], allow="\n")
    assert not _unsafe_in(payload["stack"], allow="\n")


@given(message=_safe_texts)
def test_safe_text_passes_unchanged(message: str) -> None:
    assert PlainFormatter().format(_record(message)).endswith(f" {message}")
    assert json.loads(JsonFormatter().format(_record(message)))["message"] == message


def test_every_unsafe_character_is_escaped() -> None:
    # Exhaustive, so a Python whose Unicode adds a format character fails here.
    record = _record(_UNSAFE)
    record.stack_info = _UNSAFE
    message_line, stack = PlainFormatter().format(record).split("\n", 1)
    assert not _unsafe_in(message_line)
    assert _unsafe_in(stack) == {"\n"}
    payload = json.loads(JsonFormatter().format(record))
    assert not _unsafe_in(payload["message"])
    assert _unsafe_in(payload["stack"]) == {"\n"}


@pytest.mark.parametrize(
    ("char", "escape"),
    [
        ("\N{LINE SEPARATOR}", "\\u2028"),
        ("\N{PARAGRAPH SEPARATOR}", "\\u2029"),
        ("\N{RIGHT-TO-LEFT OVERRIDE}", "\\u202e"),
        ("\N{ZERO WIDTH NO-BREAK SPACE}", "\\ufeff"),
        ("\N{SOFT HYPHEN}", "\\xad"),
        ("\N{TAG LATIN CAPITAL LETTER A}", "\\U000e0041"),
    ],
)
def test_unsafe_character_becomes_its_escape(char: str, escape: str) -> None:
    text, escaped = f"a{char}b", f"a{escape}b"
    assert PlainFormatter().format(_record(text)).endswith(f" {escaped}")
    assert PlainFormatter().format(_record("hi", name=text)).endswith(f" {escaped} hi")
    plain = PlainFormatter().format(_error_record(text))
    assert f"ValueError: {escaped}\n" in plain
    assert plain.endswith(f"\n  {escaped}")
    payload = json.loads(JsonFormatter().format(_record(text, name=text)))
    assert payload["message"] == payload["logger"] == escaped
    payload = json.loads(JsonFormatter().format(_error_record(text)))
    assert payload["exc"].endswith(f"ValueError: {escaped}")
    assert payload["stack"].endswith(f"\n  {escaped}")
