#!/bin/bash
# Run after changing the pinned Liza release or the shim: activates a throwaway clone
# of HEAD and checks that activation stays local-scope and idempotent, that a failed
# init leaves the committed settings alone, and that deactivate.sh undoes activation.

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

# Stubbed runs use $stub_home as HOME, so a stub script stands in for Liza's init.
stub="$stub_home/.liza/libexec/liza"
mkdir -p "$(dirname "$stub")" "$stub_home/.claude"
liza_dir=$(dirname "$shim")
# The stub runs the script on stdin. In it, `settings <jq filter>` edits settings.json as
# init's merge does, and $hook is a filter adding one Liza-like hook.
stub_liza() {
    {
        cat <<'EOF'
#!/bin/sh
settings() { jq "$1" .claude/settings.json >.claude/t.json && mv .claude/t.json .claude/settings.json; }
hook='.hooks.SessionStart = [{hooks: [{type: "command", command: "s"}]}]'
EOF
        cat
    } >"$stub"
    chmod +x "$stub"
}
# A fresh clone of HEAD with empty local settings; prints its path.
stub_clone() {  # name
    git clone -q "$repo" "$stub_home/$1" && echo '{}' >"$stub_home/$1/.claude/settings.local.json" \
        && echo "$stub_home/$1"
}
stub_init() { (cd "$1" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null); }  # clone
stub_deactivate() { (cd "$1" && HOME="$stub_home" bash "$liza_dir/deactivate.sh"); }  # clone

for scenario in "fails:exit 1" \
    "truncates the settings:printf '{\"hooks\":' >.claude/settings.json" \
    "empties the hooks:echo '{\"hooks\":{\"SessionStart\":[]}}' >.claude/settings.json" \
    "skips the merge:true" \
    "merges then fails:settings \"\$hook\"; exit 1"; do
    name=${scenario%%:*}
    echo "${scenario#*:}" | stub_liza
    stub_init "$clone" 2>/dev/null
    stub_rc=$?
    check "init exits non-zero when liza $name" test "$stub_rc" -ne 0
    check "local settings intact when liza $name" cmp -s .claude/settings.local.json "$personal_copy"
    check "committed settings.json untouched when liza $name" git diff --quiet -- .claude/settings.json
    check "no contract linked when liza $name" test ! -e CLAUDE.local.md -a ! -L CLAUDE.local.md
done
# An init that overwrites a user's file and then fails leaves that file as it was.
mkdir -p .claude/hooks
echo "user file" >.claude/hooks/user.sh
printf 'echo liza >.claude/hooks/user.sh\nexit 1\n' | stub_liza
stub_init "$clone" 2>"$clone/.git/partial.err"
partial_rc=$?
liza_git_dir=$(git rev-parse --git-path liza)
replaced_dir="$liza_git_dir/replaced"
check "init that fails after overwriting a user file exits non-zero" test "$partial_rc" -ne 0
check "and puts the user file back" test "$(cat .claude/hooks/user.sh)" = "user file"
check "and keeps what it replaced, named" test "$(cat "$replaced_dir/.claude/hooks/user.sh" 2>/dev/null)" = liza \
    -a -n "$(grep -F "$replaced_dir" "$clone/.git/partial.err")"
rm -rf -- "$liza_git_dir"

# The same when init is interrupted (the whole process group, as Ctrl-C would be).
echo "user file" >.claude/hooks/user.sh
printf 'echo liza >.claude/hooks/user.sh\nsleep 30\n' | stub_liza
HOME="$stub_home" setsid "$shim" init --claude --yes </dev/null >/dev/null 2>"$clone/.git/interrupt.err" &
shim_pid=$!
for _ in $(seq 50); do
    [ "$(cat .claude/hooks/user.sh)" = liza ] && break
    sleep 0.1
done
check "the stub overwrote the user file before the interrupt" test "$(cat .claude/hooks/user.sh)" = liza
kill -INT -- "-$shim_pid"
wait "$shim_pid"
interrupt_rc=$?
check "interrupted init exits non-zero" test "$interrupt_rc" -ne 0
check "and puts the user file back" test "$(cat .claude/hooks/user.sh)" = "user file"
check "and releases the lock and the committed settings" \
    test ! -e .claude/.liza-shim.lock -a ! -e .claude/settings.json.liza-shim-held
rm -rf -- "$liza_git_dir"
rm -f .claude/hooks/user.sh && rmdir .claude/hooks
check "git status clean after the failures" test -z "$(git status --porcelain)"

# The pre-activation state, with a hook of the user's own, for the deactivation checks.
exclude_file=$(git rev-parse --git-path info/exclude)
jq '.hooks.PreToolUse = [{matcher: "Bash", hooks: [{type: "command", command: "echo mine"}]}]' \
    "$personal_copy" >.claude/settings.local.json
pre_activation="$clone/.git/pre-activation-settings.local.json"
cp .claude/settings.local.json "$pre_activation"
cp "$exclude_file" "$clone/.git/pre-activation-exclude"
files_before=$(git status --porcelain --ignored)
git_files() {
    ls -A "$(git rev-parse --git-path hooks)"
    (shopt -s nullglob && cd "$(git rev-parse --absolute-git-dir)" && printf '%s\n' liza*)
}
git_files_before=$(git_files)

check "deactivate before any activation succeeds" bash "$liza_dir/deactivate.sh"
check "and leaves the local settings alone" cmp -s .claude/settings.local.json "$pre_activation"

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

# Deactivation undoes activation and keeps an edit the user made since.
jq '.permissions.allow += ["Bash(my-own-tool:*)"]' .claude/settings.local.json >"$clone/.git/edited.json" \
    && cp "$clone/.git/edited.json" .claude/settings.local.json
jq '.permissions.allow += ["Bash(my-own-tool:*)"]' "$pre_activation" >"$clone/.git/expected.json"
check "deactivate succeeds" bash "$liza_dir/deactivate.sh"
check "local settings are the user's again, with the later edit" \
    test "$(jq -S . .claude/settings.local.json)" = "$(jq -S . "$clone/.git/expected.json")"
check "contract unlinked" test ! -e CLAUDE.local.md -a ! -L CLAUDE.local.md
check "exclude file as before activation" cmp -s "$exclude_file" "$clone/.git/pre-activation-exclude"
check "no activation files left" test "$(git status --porcelain --ignored)" = "$files_before"
check "git hooks and git-dir files as before activation" test "$(git_files)" = "$git_files_before"
cp .claude/settings.local.json "$clone/.git/deactivated.json"
check "second deactivate succeeds" bash "$liza_dir/deactivate.sh"
check "second deactivate changes nothing" cmp -s .claude/settings.local.json "$clone/.git/deactivated.json"

# A file activation created and the user edited since is kept, and named.
check "activation before the edited-file check succeeds" liza init --claude --yes
edited=$(jq -r '[.files[].path | select(contains("/.claude/hooks/"))][0]' \
    "$(git rev-parse --git-path liza)/activation.json")
echo "# mine" >>"$edited"
bash "$liza_dir/deactivate.sh" 2>"$clone/.git/kept.err"
check "deactivate keeps a created file the user edited" grep -qx "# mine" "$edited"
check "deactivate names the kept file" grep -q -F -- "$edited" "$clone/.git/kept.err"

# A user file at a path init writes to is overwritten by init, and restored by deactivate.
echo "user original" >"$edited"
check "activation over a user file succeeds" liza init --claude --yes
check "init overwrote the user file" test "$(cat "$edited")" != "user original"
check "deactivate succeeds after the overwrite" bash "$liza_dir/deactivate.sh"
check "deactivate restores the overwritten user file" test "$(cat "$edited")" = "user original"

# If Liza's version was edited since, the edit stays and the original goes beside it.
check "activation over the user file again succeeds" liza init --claude --yes
echo "# edited" >>"$edited"
bash "$liza_dir/deactivate.sh" 2>"$clone/.git/pre-liza.err"
check "deactivate keeps an edited overwrite" grep -qx "# edited" "$edited"
check "and saves the user's original beside it" test "$(cat "$edited.pre-liza")" = "user original"
check "and names where" grep -q -F -- "$edited.pre-liza" "$clone/.git/pre-liza.err"
rm -f -- "$edited" "$edited.pre-liza"

check "re-activation succeeds" liza init --claude --yes

# A record that can't be read: activation says so, and deactivation falls back.
echo '{' >"$(git rev-parse --git-path liza)/activation.json"
liza init --claude --yes </dev/null >/dev/null 2>"$clone/.git/corrupt.err"
check "activation over a corrupt record warns" grep -q "could not record" "$clone/.git/corrupt.err"
check "deactivate over a corrupt record succeeds" bash "$liza_dir/deactivate.sh"
check "and unlinks the contract" test ! -L CLAUDE.local.md
check "activation succeeds after a corrupt-record deactivate" liza init --claude --yes
# The same with the record gone and the contract still linked.
rm -f "$(git rev-parse --git-path liza)/activation.json"
check "deactivate with no record succeeds" bash "$liza_dir/deactivate.sh"
check "and unlinks the contract" test ! -L CLAUDE.local.md
check "activation succeeds after a no-record deactivate" liza init --claude --yes

# rtk's hook lands in an activated clone once, and not again on re-activation. The stubs
# stand in for liza (a no-op init keeps the real hooks above) and for rtk.
stub_liza </dev/null
mkdir -p "$stub_home/.liza/bin"
printf '#!/bin/sh\n' >"$stub_home/.liza/bin/rtk"
chmod +x "$stub_home/.liza/bin/rtk"
rtk_hooks() {
    jq --arg c "$stub_home/.liza/bin/rtk hook claude" \
        '[.hooks.PreToolUse[]?.hooks[]? | select(.command == $c)] | length' .claude/settings.local.json
}
for run in first second; do
    stub_init "$clone" 2>/dev/null
    check "one rtk hook after the $run stubbed activation" test "$(rtk_hooks)" = 1
done

# Re-activations that change what Liza writes, in a fresh clone with a stub liza: the
# first adds an entry, sets a key and removes one, the second swaps the entry and sets the
# key again. Deactivation restores the original, neither the swapped-out entry nor the
# first value.
merge_clone=$(stub_clone merge-clone)
echo '{"permissions":{"allow":["mine"],"defaultMode":"acceptEdits"},"model":"m0"}' \
    >"$merge_clone/.claude/settings.local.json"
cp "$merge_clone/.claude/settings.local.json" "$merge_clone/.git/original.json"
stub_liza <<'EOF'
settings "$hook"
settings '.permissions.allow += ["liza-1"] | .model = "m1" | del(.permissions.defaultMode)'
EOF
stub_init "$merge_clone" 2>/dev/null
stub_liza <<'EOF'
settings '.permissions.allow = (.permissions.allow - ["liza-1"] + ["liza-2"]) | .model = "m2"'
EOF
stub_init "$merge_clone" 2>/dev/null
check "re-activations changed the settings" jq -e '.model == "m2"' "$merge_clone/.claude/settings.local.json"
stub_deactivate "$merge_clone"
check "deactivate after changing re-activations restores the original" \
    test "$(jq -S . "$merge_clone/.claude/settings.local.json")" = "$(jq -S . "$merge_clone/.git/original.json")"

# An init that removes a user's file or replaces their symlink, with a stub liza:
# deactivate restores both.
gone_clone=$(stub_clone gone-clone)
mkdir -p "$gone_clone/.claude/hooks" "$gone_clone/.claude/links"
echo "user file" >"$gone_clone/.claude/hooks/removed.sh"
ln -s /user/target "$gone_clone/.claude/links/linked.sh"
stub_liza <<'EOF'
rm -f .claude/hooks/removed.sh .claude/links/linked.sh
echo liza >.claude/links/linked.sh
echo liza >.claude/links/created.sh
ln -s "/liza target" .claude/links/created-link.sh
settings "$hook"
EOF
stub_init "$gone_clone" 2>/dev/null
check "the stub init removed the user's file" test ! -e "$gone_clone/.claude/hooks/removed.sh"
# A deactivate that fails part-way (here: the links directory is read-only, so restoring
# the symlink and removing the created file fail while the other restore succeeds) keeps
# the record, originals and exclude lines, and a rerun finishes without taking the
# already-restored file for an edit. Root ignores the permissions this relies on.
if [ "$(id -u)" != 0 ]; then
    gone_record="$(git -C "$gone_clone" rev-parse --absolute-git-dir)/liza"
    chmod a-w "$gone_clone/.claude/links"
    stub_deactivate "$gone_clone" 2>/dev/null
    failed_rc=$?
    chmod u+w "$gone_clone/.claude/links"
    check "a deactivate that can't restore fails" test "$failed_rc" -ne 0
    check "and keeps the record and originals for a rerun" \
        test -f "$gone_record/activation.json" -a -d "$gone_record/originals"
    check "and keeps the leftover file hidden" grep -qx /.claude/links/created.sh "$gone_clone/.git/info/exclude"
fi
stub_deactivate "$gone_clone" 2>"$stub_home/rerun.err"
rerun_rc=$?
check "deactivate (re)run succeeds" test "$rerun_rc" -eq 0
check "the rerun takes no restored file for an edit" \
    test ! -e "$gone_clone/.claude/hooks/removed.sh.pre-liza" -a ! -s "$stub_home/rerun.err"
check "the rerun removes the created file and its exclude line" \
    bash -c "test ! -e '$gone_clone/.claude/links/created.sh' \
        && ! grep -qx /.claude/links/created.sh '$gone_clone/.git/info/exclude'"
check "and a created symlink whose target has a space" test ! -L "$gone_clone/.claude/links/created-link.sh"
check "deactivate restores a user file init removed" \
    test "$(cat "$gone_clone/.claude/hooks/removed.sh")" = "user file"
check "deactivate restores a user symlink init replaced" \
    test "$(readlink "$gone_clone/.claude/links/linked.sh")" = /user/target

# A backup that can't be made (an unreadable user file) stops init before it runs. The
# stub liza succeeds on its own, so only the refusal can fail this activation.
if [ "$(id -u)" != 0 ]; then
    refuse_clone=$(stub_clone refuse-clone)
    mkdir -p "$refuse_clone/.claude/hooks"
    stub_liza <<'EOF'
settings "$hook"
EOF
    echo "user file" >"$refuse_clone/.claude/hooks/unreadable.sh"
    chmod 000 "$refuse_clone/.claude/hooks/unreadable.sh"
    stub_init "$refuse_clone" 2>"$stub_home/refuse.err"
    refuse_rc=$?
    chmod 600 "$refuse_clone/.claude/hooks/unreadable.sh"
    check "init refuses when a backup fails" test "$refuse_rc" -ne 0
    check "and says nothing was changed" grep -q "could not back up" "$stub_home/refuse.err"
    check "and leaves the clone untouched" \
        test "$(cat "$refuse_clone/.claude/hooks/unreadable.sh")" = "user file" -a ! -L "$refuse_clone/CLAUDE.local.md"
fi

# The next two scenarios' stub liza overwrites a user file, .claude/keep/f.sh.
stub_liza <<'EOF'
echo liza >.claude/keep/f.sh
settings "$hook"
EOF

# Saving a .pre-liza copy fails (read-only directory): the original isn't lost, and a rerun
# saves it.
if [ "$(id -u)" != 0 ]; then
    preliza_clone=$(stub_clone preliza-clone)
    mkdir -p "$preliza_clone/.claude/keep"
    echo "user file" >"$preliza_clone/.claude/keep/f.sh"
    stub_init "$preliza_clone" 2>/dev/null
    echo "# edited" >>"$preliza_clone/.claude/keep/f.sh"
    chmod a-w "$preliza_clone/.claude/keep"
    stub_deactivate "$preliza_clone" 2>/dev/null
    preliza_rc=$?
    chmod u+w "$preliza_clone/.claude/keep"
    check "a deactivate that can't save a .pre-liza copy fails" test "$preliza_rc" -ne 0
    check "and keeps the original for a rerun" test -d "$preliza_clone/.git/liza/originals"
    stub_deactivate "$preliza_clone" 2>/dev/null
    check "the rerun saves the .pre-liza copy" \
        test "$(cat "$preliza_clone/.claude/keep/f.sh.pre-liza" 2>/dev/null)" = "user file"
fi

# An original saved before the record's write failed (a corrupt record here): deactivate
# puts it beside the file instead of dropping it with the rest of the record.
orphan_clone=$(stub_clone orphan-clone)
mkdir -p "$orphan_clone/.claude/keep" "$orphan_clone/.git/liza"
echo "user file" >"$orphan_clone/.claude/keep/f.sh"
echo '{' >"$orphan_clone/.git/liza/activation.json"
stub_init "$orphan_clone" 2>/dev/null
stub_deactivate "$orphan_clone" 2>"$stub_home/orphan-deactivate.err"
check "deactivate saves an unrecorded original beside its file" \
    test "$(cat "$orphan_clone/.claude/keep/f.sh.pre-liza" 2>/dev/null)" = "user file"
check "and names it" grep -q -F -- "f.sh.pre-liza" "$stub_home/orphan-deactivate.err"

# Files under Liza's own exclude lines: one its tools generate goes, edited or not; one the
# user had before activation stays.
generated_clone=$(stub_clone generated-clone)
echo "user file" >"$generated_clone/insights.json"
stub_liza <<'EOF'
printf 'insights.json\ngenerated.log\n' >>.git/info/exclude
settings "$hook"
EOF
stub_init "$generated_clone" 2>/dev/null
echo "# edited" >>"$generated_clone/insights.json"
echo liza >"$generated_clone/generated.log"
check "deactivate over generated files succeeds" stub_deactivate "$generated_clone"
check "and removes a generated file" test ! -e "$generated_clone/generated.log"
check "and keeps one the user had before activation, with its edit" grep -qx "# edited" "$generated_clone/insights.json"

# A re-activation that rewrites a file init had overwritten (a Liza pin bump): deactivate
# still restores the user's original in place.
reinit_clone=$(stub_clone reinit-clone)
mkdir -p "$reinit_clone/.claude/keep"
echo "user file" >"$reinit_clone/.claude/keep/f.sh"
for version in 1 2; do
    stub_liza <<EOF
echo liza-$version >.claude/keep/f.sh
settings "\$hook"
EOF
    stub_init "$reinit_clone" 2>/dev/null
done
check "re-activation rewrote the overwritten file" test "$(cat "$reinit_clone/.claude/keep/f.sh")" = liza-2
check "deactivate after the rewrite succeeds" stub_deactivate "$reinit_clone"
check "and restores the user's original in place" \
    test "$(cat "$reinit_clone/.claude/keep/f.sh")" = "user file" -a ! -e "$reinit_clone/.claude/keep/f.sh.pre-liza"

# Originals with no record and no contract link (an activation interrupted before either):
# deactivate still saves them beside their files.
interrupted_clone=$(stub_clone interrupted-clone)
mkdir -p "$interrupted_clone/.git/liza/originals/.claude/keep" "$interrupted_clone/.claude/keep"
echo "user file" >"$interrupted_clone/.git/liza/originals/.claude/keep/f.sh"
echo liza >"$interrupted_clone/.claude/keep/f.sh"
stub_deactivate "$interrupted_clone" 2>/dev/null
check "deactivate saves originals left without a record" \
    test "$(cat "$interrupted_clone/.claude/keep/f.sh.pre-liza" 2>/dev/null)" = "user file"

# --tools undoes the toolchain's changes, and only with --tools. A stub claude logs its
# calls; a stub ~/.claude.json holds the local context7 registration and the
# codebase-memory-mcp switch-off.
tools_home="$stub_home/tools"
mkdir -p "$tools_home/bin"
cat >"$tools_home/bin/claude" <<EOF
#!/bin/sh
echo "\$*" >>"$tools_home/claude-calls"
[ -z "\${CLAUDE_STUB_FAIL:-}" ]
EOF
chmod +x "$tools_home/bin/claude"
jq -n --arg p "$clone" \
    '{projects: {($p): {mcpServers: {context7: {}}, disabledMcpServers: ["other", "codebase-memory-mcp"]}}}' \
    >"$tools_home/.claude.json"
cp .claude/settings.local.json "$clone/.git/before-tools.json"
HOME="$tools_home" PATH="$tools_home/bin:$PATH" bash "$liza_dir/deactivate.sh" --tools
check "--tools removes context7" grep -qx "mcp remove --scope local context7" "$tools_home/claude-calls"
check "--tools re-enables codebase-memory-mcp" \
    test "$(jq -c --arg p "$clone" '.projects[$p].disabledMcpServers' "$tools_home/.claude.json")" = '["other"]'
check "--tools leaves the settings alone" cmp -s .claude/settings.local.json "$clone/.git/before-tools.json"
rm -f "$tools_home/claude-calls"
jq -n '{mcpServers: {context7: {}}}' >"$tools_home/.claude.json"
HOME="$tools_home" PATH="$tools_home/bin:$PATH" bash "$liza_dir/deactivate.sh" --tools
check "--tools leaves a user-scope context7 alone" test ! -e "$tools_home/claude-calls"
jq -n --arg p "$clone" '{projects: {($p): {mcpServers: {context7: {}}}}}' >"$tools_home/.claude.json"
HOME="$tools_home" CLAUDE_STUB_FAIL=1 PATH="$tools_home/bin:$PATH" bash "$liza_dir/deactivate.sh" --tools 2>/dev/null
tools_failed_rc=$?
check "--tools fails when a removal fails" test "$tools_failed_rc" -ne 0
rm -f "$tools_home/claude-calls"

mkdir .claude/.liza-shim.lock
bash "$liza_dir/deactivate.sh" 2>/dev/null
lock_rc=$?
rmdir .claude/.liza-shim.lock
check "deactivate refuses while an init holds the lock" test "$lock_rc" -ne 0

PATH="$tools_home/bin:$PATH" bash "$liza_dir/deactivate.sh"
check "plain deactivate leaves the toolchain alone" test ! -e "$tools_home/claude-calls"

exit $((failures > 0))
