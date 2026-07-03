"""Smoke test. Replace with real tests.

Exists so `pytest` is green (exit 0, not exit 5 "no tests collected") on a fresh
template, and proves the package imports and its CLI entry point runs.
"""

import pytest

from app.__main__ import main

pytestmark = pytest.mark.unit


def test_cli_runs() -> None:
    assert main([]) == 0
