"""Print which of `ci.yml`'s gated jobs a change needs.

The `changes` job runs this and appends what it prints to `$GITHUB_OUTPUT`:
``devcontainer=true`` when the dev container job must run, ``python=true`` when
the `python` and `test` jobs must, and nothing for a job that can be skipped.
`check` counts a skipped job as passing, so a path wrongly skipped here skips
its checks and the PR still merges green.

The change is the diff from the run's base to HEAD. A pull request's base is the
first parent of its merge commit, which is the base branch. A push's base is the
previous tip, when the history holds it. With no base (a scheduled or manual
run, a new branch, a force push) every gated job runs, rather than risk skipping
a change.

Usage: ``changes.py EVENT [BEFORE]``, with the event name and, for a push, the
previous tip, in a checkout; or ``changes.py --paths [PATH ...]`` to print the
outputs for those changed paths. Standard library only, so the job needs
nothing but the runner's ``python3``.
"""

import re
import shlex
import subprocess
import sys
from collections.abc import Sequence

# What the dev container build needs (post-create.sh reads uv's pin from
# ci/requirements.txt) and the .gitignore that verify.sh's clean-status check
# depends on. Other dependency manifests are left out on purpose
# (docs/scaffold.md, CI).
_DEVCONTAINER_INPUTS = (
    r"^\.devcontainer/",
    r"^\.github/workflows/ci\.yml$",
    r"^Makefile$",
    r"^\.gitignore$",
    r"^ci/requirements\.txt$",
)
# The paths the Python jobs don't read.
_PYTHON_SKIPS = (
    r"\.md$",
    r"^docs/",
    r"^\.claude/",
    r"^\.github/",
    r"^\.pre-commit-config\.yaml$",
)
# The exceptions inside those paths that the Python jobs do read: README.md (the
# package's readme), Markdown under src/ or tests/, and ci.yml, which defines
# them. A skipped file that a Python job comes to use, such as a local action
# under .github/actions/, joins this list.
_PYTHON_READS = (
    r"^README\.md$",
    r"^(src|tests)/",
    r"^\.github/workflows/ci\.yml$",
)


def outputs(changed: Sequence[str] | None) -> list[str]:
    """Return the names of the outputs a change sets to true.

    The Python jobs are skipped only when the change names files and every one
    of them is skippable, so an empty diff runs them.

    Args:
        changed: The changed paths, or None when the run has no base.

    Returns:
        ``devcontainer``, ``python``, both or neither, in that order.
    """
    if changed is None:
        return ["devcontainer", "python"]
    names: list[str] = []
    if any(_matches(path, _DEVCONTAINER_INPUTS) for path in changed):
        names.append("devcontainer")
    if not changed or any(_needs_python(path) for path in changed):
        names.append("python")
    return names


def _needs_python(path: str) -> bool:
    return _matches(path, _PYTHON_READS) or not _matches(path, _PYTHON_SKIPS)


def _matches(path: str, patterns: Sequence[str]) -> bool:
    return any(re.search(pattern, path) for pattern in patterns)


def changed_paths(event: str, before: str) -> list[str] | None:
    """Return the paths the run's change touches, from git in the working directory.

    Args:
        event: The workflow's event name.
        before: For a push, the previous tip; ignored for other events.

    Returns:
        The paths, or None when the run has no base. A renamed file lists its
        old path too, so moving a matched file away still counts.

    Raises:
        subprocess.CalledProcessError: The diff failed.
    """
    match event:
        case "pull_request":
            base = "HEAD^1"
        case "push" if _is_commit(before):
            base = before
        case _:
            return None
    # git quotes a path holding a non-ASCII or control character, a double quote or
    # a backslash, so the patterns miss it: such a path runs the Python jobs and
    # not the dev container job, even under .devcontainer/.
    diff = subprocess.run(  # noqa: S603 -- fixed git command; base is HEAD^1 or a verified commit
        ["git", "diff", "--no-renames", "--name-only", base, "HEAD"],  # noqa: S607 -- the runner's git
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=True,
    )
    return diff.stdout.splitlines()


def _is_commit(revision: str) -> bool:
    found = subprocess.run(  # noqa: S603 -- fixed git command; a bad revision only fails the lookup
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],  # noqa: S607 -- the runner's git
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return found.returncode == 0


def main(argv: list[str]) -> int:
    """Print an ``<output>=true`` line for each gated job the change needs.

    Args:
        argv: The event name and optionally the previous tip; or ``--paths``
            and the changed paths.

    Returns:
        The exit status: 0; 1 when git fails, with nothing printed; 2 for bad
        arguments.
    """
    match argv:
        case ["--paths", *paths]:
            changed: list[str] | None = paths
        case [event, *before] if len(before) <= 1 and not event.startswith("-"):
            try:
                changed = changed_paths(event, before[0] if before else "")
            except subprocess.CalledProcessError as error:
                sys.stderr.write(f"{shlex.join(error.cmd)} exited {error.returncode}\n")
                return 1
        case _:
            sys.stderr.write(
                "usage: changes.py EVENT [BEFORE]\n       changes.py --paths [PATH ...]\n"
            )
            return 2
    sys.stdout.writelines(f"{name}=true\n" for name in outputs(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
