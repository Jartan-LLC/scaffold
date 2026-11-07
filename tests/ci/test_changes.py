"""Tests for `ci/changes.py`, which decides which of `ci.yml`'s gated jobs run.

A path the script wrongly skips passes CI green; these tests are what catch it.
The script runs as the workflow runs it, a subprocess: the path table gives it
the changed paths, and the git tests run it in a throwaway repository.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "ci" / "changes.py"

NONE = ""
DEVCONTAINER = "devcontainer=true\n"
PYTHON = "python=true\n"
BOTH = DEVCONTAINER + PYTHON

# The git tests must not see the repository the suite runs in, which GIT_DIR or
# GIT_INDEX_FILE point at inside a git hook, nor the user's config.
GIT_ENV = {
    **{name: value for name, value in os.environ.items() if not name.startswith("GIT_")},
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # git looks no higher than cwd for a repository, so a test run in a
    # directory that is no repository finds none.
    env = GIT_ENV if cwd is None else GIT_ENV | {"GIT_CEILING_DIRECTORIES": str(cwd.parent)}
    return subprocess.run(  # noqa: S603 -- fixed interpreter and script, test-owned arguments
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=env,
    )


# One row per path class `docs/scaffold.md`'s CI section names, and each of the
# dev container job's build inputs.
PATHS = [
    pytest.param(["docs/conf.py"], NONE, id="docs/"),
    pytest.param([".claude/settings.json"], NONE, id=".claude/"),
    pytest.param([".github/dependabot.yml"], NONE, id=".github/"),
    pytest.param([".github/workflows/release.yml"], NONE, id="other workflow"),
    pytest.param([".github/workflows/ci.yml"], BOTH, id="ci.yml"),
    pytest.param([".pre-commit-config.yaml"], NONE, id=".pre-commit-config.yaml"),
    pytest.param(["CONTRIBUTING.md"], NONE, id="root Markdown"),
    pytest.param(["examples/guide.md"], NONE, id="nested Markdown"),
    pytest.param(["README.md"], PYTHON, id="README.md"),
    pytest.param(["docs/README.md"], NONE, id="README.md not at the root"),
    pytest.param(["src/app/README.md"], PYTHON, id="Markdown under src/"),
    pytest.param(["tests/README.md"], PYTHON, id="Markdown under tests/"),
    pytest.param(["docs/src/page.md"], NONE, id="src/ not at the root"),
    pytest.param(["src/app/__init__.py"], PYTHON, id="src/"),
    pytest.param(["tests/test_smoke.py"], PYTHON, id="tests/"),
    pytest.param(["pyproject.toml"], PYTHON, id="pyproject.toml"),
    pytest.param(["conftest.py"], PYTHON, id="conftest.py"),
    pytest.param([".python-version"], PYTHON, id=".python-version"),
    pytest.param(["LICENSE"], PYTHON, id="LICENSE"),
    pytest.param(["ci/changes.py"], PYTHON, id="ci/ script"),
    pytest.param(["ci/requirements.txt"], BOTH, id="ci/requirements.txt"),
    pytest.param([".devcontainer/devcontainer.json"], BOTH, id=".devcontainer/"),
    pytest.param([".devcontainer/README.md"], DEVCONTAINER, id="Markdown under .devcontainer/"),
    pytest.param(["Makefile"], BOTH, id="Makefile"),
    pytest.param([".gitignore"], BOTH, id=".gitignore"),
    pytest.param(["docs/index.md", ".claude/x.md", "NOTES.md"], NONE, id="only skippable"),
    pytest.param(["docs/index.md", "src/app/__init__.py"], PYTHON, id="one Python input"),
    pytest.param(["docs/index.md", "Makefile"], BOTH, id="one dev container input"),
    pytest.param([], PYTHON, id="empty diff"),
]


@pytest.mark.parametrize(("paths", "expected"), PATHS)
def test_changed_paths_set_the_outputs(paths: list[str], expected: str) -> None:
    result = run("--paths", *paths)
    assert result.returncode == 0
    assert result.stdout == expected


@pytest.mark.parametrize(
    ("event", "before"),
    [
        pytest.param("schedule", "", id="scheduled"),
        pytest.param("workflow_dispatch", "", id="manual"),
        pytest.param("merge_group", "", id="other event"),
    ],
)
def test_run_with_no_base_runs_every_gated_job(tmp_path: Path, event: str, before: str) -> None:
    # tmp_path is no repository, so a git call would fail the run.
    result = run(event, before, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == BOTH


def git(repo: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 -- git with test-owned arguments
        ["git", *args],  # noqa: S607 -- the git on PATH, as the workflow uses
        cwd=repo,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def commit(repo: Path, *paths: str) -> str:
    for path in paths:
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"{path}\n")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--allow-empty", "--message", "change")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "--quiet", "--initial-branch", "main")
    commit(tmp_path, "README.md")
    return tmp_path


def test_pull_request_diffs_from_the_merge_commits_first_parent(repo: Path) -> None:
    # GIVEN a merge commit whose first parent, the base branch, has moved on
    # with a dev container change the pull request doesn't make
    git(repo, "switch", "--quiet", "--create", "feature")
    commit(repo, "src/app/__init__.py")
    git(repo, "switch", "--quiet", "main")
    commit(repo, ".devcontainer/devcontainer.json")
    git(repo, "merge", "--quiet", "--no-ff", "--no-edit", "feature")
    # THEN only the pull request's own change counts
    assert run("pull_request", "", cwd=repo).stdout == PYTHON


def test_push_diffs_from_the_previous_tip(repo: Path) -> None:
    # GIVEN a push of two commits, the last of them docs only
    before = git(repo, "rev-parse", "HEAD")
    commit(repo, "src/app/__init__.py")
    commit(repo, "docs/index.md")
    # THEN both commits count
    assert run("push", before, cwd=repo).stdout == PYTHON


def test_push_of_docs_only_skips_every_gated_job(repo: Path) -> None:
    before = git(repo, "rev-parse", "HEAD")
    commit(repo, "docs/index.md")
    assert run("push", before, cwd=repo).stdout == NONE


@pytest.mark.parametrize(
    "before",
    [
        pytest.param("0" * 40, id="new branch"),
        pytest.param("1" * 40, id="force push, previous tip not fetched"),
        pytest.param("", id="empty"),
    ],
)
def test_push_with_no_previous_tip_runs_every_gated_job(repo: Path, before: str) -> None:
    commit(repo, "docs/index.md")
    assert run("push", before, cwd=repo).stdout == BOTH


def test_rename_counts_the_old_path(repo: Path) -> None:
    # GIVEN a file moved out of .devcontainer/ into a skipped path
    commit(repo, ".devcontainer/notes.md")
    before = git(repo, "rev-parse", "HEAD")
    (repo / "docs").mkdir()
    git(repo, "mv", ".devcontainer/notes.md", "docs/notes.md")
    commit(repo)
    # THEN the dev container job runs, as for any change under .devcontainer/
    assert run("push", before, cwd=repo).stdout == DEVCONTAINER


def test_git_failure_fails_with_nothing_printed(repo: Path) -> None:
    # GIVEN a checkout without HEAD's parent, as a too-shallow fetch leaves it
    result = run("pull_request", cwd=repo)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "git diff --no-renames --name-only 'HEAD^1' HEAD exited" in result.stderr


@pytest.mark.parametrize("args", [[], ["push", "abc", "extra"], ["--help"]])
def test_bad_arguments_exit_2_with_usage(args: list[str]) -> None:
    result = run(*args)
    assert result.returncode == 2
    assert result.stderr == (
        "usage: changes.py EVENT [BEFORE]\n       changes.py --paths [PATH ...]\n"
    )
    assert result.stdout == ""
