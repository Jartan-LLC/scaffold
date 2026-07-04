"""Shared pytest fixtures."""

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
