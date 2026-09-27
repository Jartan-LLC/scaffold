#!/bin/bash
# Checks that post-create.sh left this container as ACTIVATE_LIZA and INSTALL_LIZA_TOOLS
# say; post-create itself only warns. CI runs it in a fresh container.

set -uo pipefail
failures=0
check() {  # description  command...
    if "${@:2}" >/dev/null 2>&1 </dev/null; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}

check "Claude Code CLI runs" claude --version
check "pnpm available" pnpm --version
check "pre-commit hook wired" test -f "$(git rev-parse --git-path hooks)/pre-commit"
if [ "${ACTIVATE_LIZA:-false}" = true ]; then
    check "Liza activated and recorded" test -L CLAUDE.local.md -a -f "$(git rev-parse --git-path liza)/activation.json"
else
    check "Liza not activated" test ! -e CLAUDE.local.md
fi
if [ "${INSTALL_LIZA_TOOLS:-false}" = true ]; then
    # shellcheck disable=SC2016 # $t expands in the inner bash
    check "Liza toolchain installed" bash -c 'cd ~/.liza/bin && for t in rg ast-grep yq stacklit scip-search \
        functional-clusters mdtoc bash-policy semble; do [ -x "$t" ] || exit 1; done'
    check "context7 registered" claude mcp get context7
else
    check "codebase-memory-mcp registered" claude mcp get codebase-memory-mcp
fi
check "git status clean" test -z "$(git status --porcelain)"
exit $((failures > 0))
