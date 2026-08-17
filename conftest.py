"""Fixtures shared by every collected test.

At the repo root, not in `tests/`, because `--doctest-modules` collects docstring
examples from `src/` and a `tests/conftest.py` would not reach them. A fixture
only the `tests/` suite needs can still go in a `tests/conftest.py`.
"""

import logging
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]  # invoked by pytest
    """Save and restore the root logger so ``setup_logging`` calls don't leak across tests."""
    root = logging.getLogger()
    level, handlers = root.level, root.handlers[:]
    yield
    root.setLevel(level)
    root.handlers[:] = handlers
