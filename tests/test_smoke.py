"""Smoke test: the package imports and its command-line entry point runs."""

import pytest

from app.__main__ import main

pytestmark = pytest.mark.unit


def test_cli_runs() -> None:
    assert main([]) == 0
