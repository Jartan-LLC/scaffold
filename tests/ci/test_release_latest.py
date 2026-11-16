"""Tests for `release.yml`'s Create GitHub Release step.

They cover which full release it marks Latest, which the Pages workflow serves, and
what a re-run does to the release an earlier run of the tag left. The release job
runs no repository code, so these rules live in that step. Each test runs the step's
script as the runner does, with ``bash -e``, and a stub ``gh`` first on ``PATH``
that finds the tag's release in the given state, lists the given releases, and
records each call and the arguments ``gh release create`` gets.
"""

import os
import subprocess
import textwrap
from pathlib import Path
from typing import Literal, NamedTuple

import pytest

pytestmark = pytest.mark.unit

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"

GH = """\
#!/usr/bin/env bash
printf '%s\\n' "$*" >>"$CALLS"
case "$1 $2" in
    "release view")
        case "$RELEASE" in
            draft) echo true ;;
            published) echo false ;;
            *) echo "release not found" >&2; exit 1 ;;
        esac
        ;;
    "release delete") ;;
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


class Step(NamedTuple):
    """What a run of the step did."""

    calls: list[str]
    created: list[str]
    output: str


def run_step(
    tmp_path: Path,
    tag: str,
    releases: list[str],
    release: Literal["none", "draft", "published"] = "none",
) -> Step:
    """Runs the step with ``release`` the state of the tag's own release.

    ``Step.created`` is empty when ``gh release create`` didn't run.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH, encoding="utf-8")
    gh.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(step_script(), encoding="utf-8")
    calls = tmp_path / "calls"
    created = tmp_path / "created"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TAGS": "".join(f"{r}\n" for r in releases),
        "RELEASE": release,
        "CALLS": str(calls),
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
    return Step(
        calls=calls.read_text(encoding="utf-8").splitlines(),
        created=created.read_text(encoding="utf-8").splitlines() if created.exists() else [],
        output=result.stdout,
    )


@pytest.mark.parametrize(
    ("tag", "releases", "latest"),
    [
        pytest.param("v1.0.0", [], "--latest", id="first release"),
        pytest.param("v1.10.0", ["v1.9.0"], "--latest", id="1.10 above 1.9"),
        pytest.param("v1.9.1", ["v1.10.0", "v1.9.0"], "--latest=false", id="lower after higher"),
        pytest.param("v1.10.0", ["v1.10.0", "v1.9.0"], "--latest", id="re-run of the highest"),
        pytest.param("v2.0.0", ["weekly", "v1.0.0"], "--latest", id="non-version tag"),
        pytest.param("v2.0.0", ["vnext", "v1.0.0"], "--latest", id="v and no digit"),
        pytest.param("vnext", ["v1.0.0"], "--latest=false", id="non-version tag released"),
        pytest.param("vnext", [], "--latest=false", id="non-version tag, no version releases"),
    ],
)
def test_latest_goes_to_the_highest_full_release(
    tmp_path: Path, tag: str, releases: list[str], latest: str
) -> None:
    created = run_step(tmp_path, tag, releases).created
    assert [arg for arg in created if arg.startswith("--latest")] == [latest]


NOT_A_VERSION = "::notice::vnext doesn't start with v and a digit, so it is not marked Latest"


@pytest.mark.parametrize(
    ("tag", "releases", "notice"),
    [
        pytest.param(
            "v1.9.1",
            ["v1.10.0"],
            "::notice::v1.10.0 is a higher full release, so v1.9.1 is not marked Latest",
            id="lower after higher",
        ),
        pytest.param("vnext", ["v1.0.0"], NOT_A_VERSION, id="non-version tag released"),
        pytest.param("vnext", [], NOT_A_VERSION, id="non-version tag, no version releases"),
    ],
)
def test_the_notice_says_why_a_release_is_not_latest(
    tmp_path: Path, tag: str, releases: list[str], notice: str
) -> None:
    output = run_step(tmp_path, tag, releases).output
    assert notice in output.splitlines()


def subcommands(step: Step) -> list[str]:
    return [call.split()[1] for call in step.calls]


def test_a_rerun_after_the_release_published_changes_nothing(tmp_path: Path) -> None:
    step = run_step(tmp_path, "v1.0.0", ["v1.0.0"], release="published")
    assert subcommands(step) == ["view"]


def test_a_rerun_replaces_the_draft_a_cancelled_upload_left(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.noarch.rpm").touch()
    step = run_step(tmp_path, "v1.0.0", [], release="draft")
    assert subcommands(step) == ["view", "delete", "list", "create"]
    assert "release view v1.0.0 --json isDraft --jq .isDraft" in step.calls
    assert "release delete v1.0.0 --yes" in step.calls
    notice = "::notice::v1.0.0 has a draft release; deleting it to create the release again"
    assert notice in step.output.splitlines()
    assert "assets/app.noarch.rpm" in step.created
    assert "--latest" in step.created
