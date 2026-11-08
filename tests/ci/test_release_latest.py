"""Tests for which full release `release.yml` marks Latest, which the Pages workflow serves.

The release job runs no repository code, so the rule lives in its Create GitHub
Release step. Each test runs that step's script as the runner does, with
``bash -e``, and a stub ``gh`` first on ``PATH`` that lists the given releases
and records the arguments ``gh release create`` gets.
"""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"

GH = """\
#!/usr/bin/env bash
case "$1 $2" in
    "release view") exit 1 ;;
    "release list") printf '%s' "$TAGS" ;;
    "release create") shift 2; printf '%s\\n' "$@" >"$CREATED" ;;
    *) echo "unexpected: gh $*" >&2; exit 2 ;;
esac
"""


def step_script() -> str:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index("      - name: Create GitHub Release")
    run = next(i for i in range(start, len(lines)) if lines[i] == "        run: |")
    body: list[str] = []
    for line in lines[run + 1 :]:
        if line and not line.startswith(" " * 10):
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)) + "\n"


def created_args(tmp_path: Path, tag: str, releases: list[str]) -> list[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH, encoding="utf-8")
    gh.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(step_script(), encoding="utf-8")
    created = tmp_path / "created"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TAGS": "".join(f"{r}\n" for r in releases),
        "CREATED": str(created),
        "GITHUB_REF_NAME": tag,
        "NOTES_SOURCE": "generated",
        "PRERELEASE": "false",
        "RUNNER_TEMP": str(tmp_path),
    }
    result = subprocess.run(  # noqa: S603 -- fixed interpreter, test-owned script
        ["bash", "-e", str(script)],  # noqa: S607 -- the runner's bash, as the step uses
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    return created.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize(
    ("tag", "releases", "latest"),
    [
        pytest.param("v1.0.0", [], "--latest", id="first release"),
        pytest.param("v1.10.0", ["v1.9.0"], "--latest", id="1.10 above 1.9"),
        pytest.param("v1.9.1", ["v1.10.0", "v1.9.0"], "--latest=false", id="lower after higher"),
        pytest.param("v1.10.0", ["v1.10.0", "v1.9.0"], "--latest", id="re-run of the highest"),
        pytest.param("v2.0.0", ["weekly", "v1.0.0"], "--latest", id="non-version tag"),
        pytest.param("v2.0.0", ["vnext", "v1.0.0"], "--latest", id="v and no digit"),
        pytest.param("weekly", ["v1.0.0"], "--latest=false", id="non-version tag released"),
    ],
)
def test_latest_goes_to_the_highest_full_release(
    tmp_path: Path, tag: str, releases: list[str], latest: str
) -> None:
    args = created_args(tmp_path, tag, releases)
    assert [arg for arg in args if arg.startswith("--latest")] == [latest]
