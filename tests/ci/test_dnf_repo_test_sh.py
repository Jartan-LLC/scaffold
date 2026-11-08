"""Tests for `ci/dnf-repo-test.sh verify`'s argument checks, which run before dnf does.

ci.yml's `dnf-repo` job tests what verify does with dnf, in Fedora; these need
no dnf, as the script refuses each bad argument first.
"""

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "ci" / "dnf-repo-test.sh"
RPM_URL = "https://example.invalid/releases/latest/download/app.noarch.rpm"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        pytest.param([RPM_URL], "usage:", id="no version"),
        pytest.param([RPM_URL, "1.0.0", "0", "extra"], "usage:", id="extra argument"),
        pytest.param(
            ["https://example.invalid/app.rpm", "1.0.0"],
            "not a URL to NAME.noarch.rpm: https://example.invalid/app.rpm",
            id="not a noarch rpm",
        ),
        pytest.param([RPM_URL, "1.0.0", "2m"], "SECONDS is not a number: 2m", id="seconds"),
    ],
)
def test_verify_refuses_bad_arguments(args: list[str], message: str) -> None:
    result = subprocess.run(  # noqa: S603 -- fixed script, test-owned arguments
        [str(SCRIPT), "verify", *args], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert result.stderr.startswith(f"dnf-repo-test.sh: {message}")
    assert result.stdout == ""
