#!/bin/bash
# Checks that post-create.sh left this container as ACTIVATE_LIZA and INSTALL_LIZA_TOOLS
# say. CI runs it in a freshly created container; it's also safe to run by hand.

set -uo pipefail

failures=0
check() {  # description  command...
    if "${@:2}" >/dev/null 2>&1 </dev/null; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}

check "Claude Code CLI runs" claude --version
check "Liza's ripgrep installed" test -x "$HOME/.liza/bin/rg"
check "pre-commit hook wired" test -f "$(git rev-parse --git-path hooks)/pre-commit"

if [ "${ACTIVATE_LIZA:-false}" = true ]; then
    check "Liza's contract linked" test "$(readlink -f CLAUDE.local.md)" = "$(readlink -f "$HOME/.liza/CORE.md")"
    check "Liza's hooks in settings.local.json" jq -e '.hooks.SessionStart | length > 0' .claude/settings.local.json
    check "activation recorded for deactivate.sh" test -f "$(git rev-parse --git-path liza)/activation.json"
else
    check "Liza not activated" test ! -e CLAUDE.local.md
fi

if [ "${INSTALL_LIZA_TOOLS:-false}" = true ]; then
    tools=(ast-grep yq stacklit scip-search functional-clusters mdtoc bash-policy semble)
    [ "$(uname -m)" = x86_64 ] && tools+=(rtk mdq)
    for tool in "${tools[@]}"; do
        check "$tool installed" test -x "$HOME/.liza/bin/$tool"
    done
    check "context7 registered" claude mcp get context7
else
    check "codebase-memory-mcp installed" command -v codebase-memory-mcp
fi

check "git status clean" test -z "$(git status --porcelain)"

exit $((failures > 0))
