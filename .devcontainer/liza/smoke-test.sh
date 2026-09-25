#!/bin/bash
# Run after changing the pinned Liza release or the shim: activates a throwaway clone
# of HEAD and checks that activation stays local-scope and idempotent, and that a
# failed init leaves the committed settings alone.

set -uo pipefail

shim=$(readlink -f "$(command -v liza)")
if [[ "$shim" != */.devcontainer/liza/shim.sh ]]; then
    echo "liza on PATH is not the shim (${shim:-not found}); run .devcontainer/liza/install.sh first." >&2
    exit 1
fi

repo=$(git rev-parse --show-toplevel) || exit 1
clone=$(mktemp -d)
stub_home=$(mktemp -d)
trap 'rm -rf "$clone" "$stub_home"' EXIT
git clone -q "$repo" "$clone" && cd "$clone" || exit 1

failures=0
check() {  # description  command...
    if "${@:2}" >/dev/null 2>&1 </dev/null; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}

# Failure paths first, on the untouched clone.
touch .claude/settings.json.liza-shim-held
liza init --claude --yes </dev/null >/dev/null 2>&1
held_rc=$?
rm .claude/settings.json.liza-shim-held
check "init refuses while a held settings file exists" test "$held_rc" -ne 0
check "committed settings.json untouched after the refusal" git diff --quiet -- .claude/settings.json

mkdir -p "$stub_home/.liza/libexec" "$stub_home/.claude"
printf '#!/bin/sh\nexit 1\n' >"$stub_home/.liza/libexec/liza"
chmod +x "$stub_home/.liza/libexec/liza"
HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>&1
stub_rc=$?
check "init passes on a failing liza's exit status" test "$stub_rc" -ne 0
check "committed settings.json untouched after the failure" git diff --quiet -- .claude/settings.json
check "no contract linked after the failure" test ! -e CLAUDE.local.md -a ! -L CLAUDE.local.md
check "git status clean after the failure" test -z "$(git status --porcelain)"

global_before=$(ls -la "$HOME/.claude/CLAUDE.md" 2>&1)
# Kept under .git/ so the snapshot never shows in the git status checks.
first_local="$clone/.git/first-settings.local.json"

check "first activation succeeds" liza init --claude --yes
cp .claude/settings.local.json "$first_local"
check "committed settings.json untouched" git diff --quiet -- .claude/settings.json
check "git status clean" test -z "$(git status --porcelain)"
check "Liza hooks in settings.local.json" jq -e '.hooks.SessionStart' .claude/settings.local.json
check "CLAUDE.local.md resolves to the contract" test "$(readlink -f CLAUDE.local.md)" = "$(readlink -f "$HOME/.liza/CORE.md")"
check "global CLAUDE.md unchanged" test "$(ls -la "$HOME/.claude/CLAUDE.md" 2>&1)" = "$global_before"
check "second activation succeeds" liza init --claude --yes
check "second activation is a no-op" test "$(jq -S . .claude/settings.local.json)" = "$(jq -S . "$first_local")"
check "git status still clean" test -z "$(git status --porcelain)"

exit $((failures > 0))
