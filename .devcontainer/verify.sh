#!/bin/bash
# Checks that this repo's dev container setup worked: pnpm from devcontainer.json and what
# post-create.sh installs, which only reports its failures. CI runs it in a fresh
# container. The enchantments Features check their own setup.

set -uo pipefail
failures=0
check() {  # description  command...
    if "${@:2}" >/dev/null 2>&1 </dev/null; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}

check "pre-commit hook wired" test -f "$(git rev-parse --git-path hooks)/pre-commit"
# Liza sets core.hooksPath in task worktrees; set here, make install skips pre-commit.
check "core.hooksPath unset" test -z "$(git config core.hooksPath)"
check "pnpm available" pnpm --version
# make install put the project into this Python; the name follows /onboard's rename.
if [ -f pyproject.toml ]; then
    pkg=$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"][0].rpartition("/")[2])')
    check "package $pkg imports" python -c "import $pkg"
    check "pytest collects the suite" pytest --collect-only -q
fi
check "git status clean" test -z "$(git status --porcelain)"
exit $((failures > 0))
