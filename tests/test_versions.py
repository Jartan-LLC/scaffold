"""Tests for `ci/versions.py --image-tags`, which names `publish-docker.yml`'s images.

The script runs as the workflow runs it, a subprocess given the pushed tag's
version and, on stdin, the repository's tags. Each test checks the tags the
image would be pushed with.
"""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[1] / "ci" / "versions.py"


def run(*args: str, tags: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- fixed interpreter and script, test-owned arguments
        [sys.executable, str(SCRIPT), *args],
        input=tags,
        capture_output=True,
        text=True,
        check=False,
    )


def outputs(version: str, *tags: str) -> str:
    result = run("--image-tags", version, tags="\n".join(tags) + "\n")
    assert result.returncode == 0, result.stderr
    return result.stdout


def release(version: str, minor: str, latest: str) -> str:
    return f"version={version}\nminor={minor}\nlatest={latest}\n"


def prerelease(version: str) -> str:
    return f"version={version}\nminor=\nlatest=false\n"


# Each row pushes the version given with the tags already in the repository,
# which hold the pushed tag too, as the workflow's checkout does.
CASES = [
    pytest.param("1.2.0", ["v1.1.0", "v1.2.0"], release("1.2.0", "1.2", "true"), id="release"),
    pytest.param(
        "1.2.0",
        ["v1.1.0", "v1.2.0rc1", "v1.2.0"],
        release("1.2.0", "1.2", "true"),
        id="release after its pep440 rc",
    ),
    pytest.param(
        "1.2.0",
        ["v1.2.0a1", "v1.2.0b1", "v1.2.0c1", "v1.2.0.dev3", "v1.2.0rc1.post1", "v1.2.0"],
        release("1.2.0", "1.2", "true"),
        id="release after pep440 pre and dev releases",
    ),
    pytest.param(
        "1.2.0",
        ["v1.2.0-rc.1", "v1.2.0-alpha", "v1.2.0"],
        release("1.2.0", "1.2", "true"),
        id="release after semver pre-releases",
    ),
    pytest.param(
        "1.2.0rc1", ["v1.1.0", "v1.2.0rc1"], prerelease("1.2.0rc1"), id="pep440 rc stays off latest"
    ),
    pytest.param(
        "1.2.0-rc.1",
        ["v1.1.0", "v1.2.0-rc.1"],
        prerelease("1.2.0-rc.1"),
        id="semver rc keeps its spelling",
    ),
    pytest.param("1.2.0.dev3", ["v1.2.0.dev3"], prerelease("1.2.0.dev3"), id="pep440 dev"),
    pytest.param(
        "1.1.5", ["v1.1.5", "v1.2.0"], release("1.1.5", "1.1", "false"), id="patch on older line"
    ),
    pytest.param(
        "1.10.0", ["v1.9.0", "v1.10.0"], release("1.10.0", "1.10", "true"), id="numeric order"
    ),
    pytest.param(
        "1.2.0.post1",
        ["v1.2.0", "v1.2.0.post1"],
        release("1.2.0.post1", "1.2", "true"),
        id="post-release",
    ),
    pytest.param(
        "1.2.0.post2",
        ["v1.2.0-post1", "v1.2.0.post2"],
        release("1.2.0.post2", "1.2", "true"),
        id="post-release spellings",
    ),
    pytest.param(
        "1.2.0.post1",
        ["v1.2.0.post1", "v1.2.0-post2"],
        release("1.2.0.post1", "1.2", "false"),
        id="below a higher post-release",
    ),
    pytest.param(
        "1.2.0-1",
        ["v1.2.0", "v1.2.0-1"],
        release("1.2.0-1", "1.2", "true"),
        id="implicit post-release",
    ),
    pytest.param(
        "1.2.0", ["v1.2.0", "v1.2.0.post1"], release("1.2.0", "1.2", "false"), id="below its post"
    ),
    pytest.param("1.2", ["v1.2.0", "v1.2"], release("1.2", "1.2", "true"), id="equal spellings"),
    pytest.param("2.0.0", ["v2.0.0"], release("2.0.0", "2.0", "true"), id="trailing zeros"),
    pytest.param("2", ["v2"], release("2", "2.0", "true"), id="one number"),
    pytest.param(
        "2.0.0", ["v1!1.0.0", "v2.0.0"], release("2.0.0", "2.0", "false"), id="below an epoch"
    ),
    pytest.param(
        "1.2.0+build.5",
        ["v1.2.0", "v1.2.0+build.5"],
        release("1.2.0", "1.2", "true"),
        id="local version",
    ),
    pytest.param(
        "1.2.0+a--b",
        ["v1.2.0", "v1.2.0+a--b"],
        release("1.2.0", "1.2", "true"),
        id="semver-only build metadata",
    ),
    pytest.param(
        "1.2.0-rc.1+build.5",
        ["v1.2.0-rc.1+build.5"],
        prerelease("1.2.0-rc.1"),
        id="pre-release build metadata",
    ),
    pytest.param(
        "1.2.0",
        ["vnext", "very-old", "v1.2.0"],
        release("1.2.0", "1.2", "true"),
        id="non-version tags ignored",
    ),
    pytest.param("1.0.0", [], release("1.0.0", "1.0", "true"), id="no tags"),
]


@pytest.mark.parametrize(("version", "tags", "expected"), CASES)
def test_image_tags(version: str, tags: list[str], expected: str) -> None:
    assert outputs(version, *tags) == expected


def test_not_highest_release_gives_a_notice() -> None:
    result = run("--image-tags", "1.1.5", tags="v1.1.5\nv1.2.0\n")
    assert result.stderr == "::notice::v1.1.5 is not the highest release; leaving :latest alone\n"


def test_prerelease_gives_a_notice() -> None:
    result = run("--image-tags", "1.2.0rc1", tags="v1.2.0rc1\n")
    assert result.stderr == "::notice::v1.2.0rc1 is a pre-release; leaving :latest alone\n"


@pytest.mark.parametrize("version", ["next", "1.2.0-foo_bar", "1.2.0,enable=false", ""])
def test_non_version_fails_with_nothing_printed(version: str) -> None:
    result = run("--image-tags", version, tags="v1.0.0\n")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        f"::error::v{version} is neither a PEP 440 nor a SemVer version, so the image gets no tags\n"
    )


@pytest.mark.parametrize("args", [[], ["1.2.0"], ["--image-tags"], ["--image-tags", "1", "2"]])
def test_bad_arguments_exit_2_with_usage(args: list[str]) -> None:
    result = run(*args)
    assert result.returncode == 2
    assert result.stderr == "usage: versions.py --image-tags VERSION\n"
    assert result.stdout == ""
