#!/bin/bash
# Checks pnpm and what post-create.sh installs in the dev container. post-create.sh only
# reports its failures, so these checks are what fails on them. Run it in a fresh
# container: the last check expects a clean git status.

set -uo pipefail
failures=0
check() {  # description  command...
    if "${@:2}" >/dev/null 2>&1 </dev/null; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}

check "pre-commit hook wired" test -f "$(git rev-parse --git-path hooks)/pre-commit"
# Liza sets core.hooksPath in task worktrees; set here, make install skips pre-commit.
check "core.hooksPath unset" test -z "$(git config core.hooksPath)"
check "pnpm available" pnpm --version
# The ruff the editor formats with, in the Python the ruff extension selects.
ruff_version=$(bash .devcontainer/ruff-version.sh)
case $? in
    0) check "ruff $ruff_version installed" test "$(python -m ruff --version 2>/dev/null)" = "ruff $ruff_version" ;;
    1) check "ruff hook rev has a '# frozen: vX.Y.Z' comment" false ;;
esac
# make install put the project into this Python; the name is pyproject.toml's
# [tool.hatch.build.targets.wheel] packages entry.
if [ -f pyproject.toml ]; then
    pkg=$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"][0].rpartition("/")[2])')
    check "package $pkg imports" python -c "import $pkg"
    check "pytest collects the suite" pytest --collect-only -q
fi
check "git status clean" test -z "$(git status --porcelain)"
exit $((failures > 0))
