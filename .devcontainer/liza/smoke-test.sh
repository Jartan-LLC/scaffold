#!/bin/bash
# Run after changing the pinned Liza release or the shim: activates a throwaway clone
# of HEAD and checks that activation stays local-scope and idempotent.

set -uo pipefail

repo=$(git rev-parse --show-toplevel) || exit 1
clone=$(mktemp -d)
trap 'rm -rf "$clone"' EXIT
git clone -q "$repo" "$clone" && cd "$clone" || exit 1

failures=0
check() {  # description  command...
    if "${@:2}" >/dev/null 2>&1 </dev/null; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}

global_before=$(ls -la "$HOME/.claude/CLAUDE.md" 2>&1)
first_local="$clone/.git/first-settings.local.json"

check "first activation succeeds" liza init --claude --yes
cp .claude/settings.local.json "$first_local"
check "committed settings.json untouched" git diff --quiet -- .claude/settings.json
check "git status clean" test -z "$(git status --porcelain)"
check "Liza hooks in settings.local.json" jq -e '.hooks.SessionStart' .claude/settings.local.json
check "CLAUDE.local.md resolves to the contract" test "$(readlink -f CLAUDE.local.md)" = "$(readlink -f "$HOME/.liza/CORE.md")"
check "global CLAUDE.md unchanged" test "$(ls -la "$HOME/.claude/CLAUDE.md" 2>&1)" = "$global_before"
check "second activation succeeds" liza init --claude --yes
check "second activation is a no-op" cmp -s .claude/settings.local.json "$first_local"
check "git status still clean" test -z "$(git status --porcelain)"

exit $((failures > 0))
