"""Command-line entry point: ``python -m app``.

TODO(/onboard): if the project has no command-line interface, delete this module,
its ``automodule`` entry in docs/reference.md, tests/test_smoke.py, which runs it,
and the Dockerfile ``CMD`` hint.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from app.log import setup_logging

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Command-line arguments, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        prog="app", description="TODO(/onboard): the CLI's one-line description."
    )
    parser.add_argument(
        "--log-format", choices=("plain", "json"), default="plain", help="Log output format."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args(argv)

    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO, fmt=args.log_format)
    logger.info("%s started", parser.prog)
    sys.stdout.write(f"Hello from {parser.prog}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
