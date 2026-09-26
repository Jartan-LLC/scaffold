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

# Failure paths first, on the untouched clone, with personal local settings to protect.
# Snapshots live under .git/ so they never show in the git status checks.
personal_copy="$clone/.git/personal-settings.local.json"
echo '{"permissions":{"allow":["Bash(echo:*)"]}}' >.claude/settings.local.json
cp .claude/settings.local.json "$personal_copy"

touch .claude/settings.json.liza-shim-held
liza init --claude --yes </dev/null >/dev/null 2>&1
held_rc=$?
rm .claude/settings.json.liza-shim-held
check "init refuses while a held settings file exists" test "$held_rc" -ne 0
check "committed settings.json untouched after the refusal" git diff --quiet -- .claude/settings.json

stub="$stub_home/.liza/libexec/liza"
mkdir -p "$(dirname "$stub")" "$stub_home/.claude"
for scenario in "fails:exit 1" \
    "truncates the settings:printf '{\"hooks\":' >.claude/settings.json" \
    "skips the merge:true"; do
    name=${scenario%%:*}
    printf '#!/bin/sh\n%s\n' "${scenario#*:}" >"$stub"
    chmod +x "$stub"
    HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>&1
    stub_rc=$?
    check "init exits non-zero when liza $name" test "$stub_rc" -ne 0
    check "local settings intact when liza $name" cmp -s .claude/settings.local.json "$personal_copy"
    check "committed settings.json untouched when liza $name" git diff --quiet -- .claude/settings.json
    check "no contract linked when liza $name" test ! -e CLAUDE.local.md -a ! -L CLAUDE.local.md
done
check "git status clean after the failures" test -z "$(git status --porcelain)"

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
check "second activation is a no-op" test "$(jq -S . .claude/settings.local.json)" = "$(jq -S . "$first_local")"
check "git status still clean" test -z "$(git status --porcelain)"

exit $((failures > 0))
