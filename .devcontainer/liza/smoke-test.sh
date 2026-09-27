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

stub="$stub_home/.liza/libexec/liza"
mkdir -p "$(dirname "$stub")" "$stub_home/.claude"
for scenario in "fails:exit 1" \
    "truncates the settings:printf '{\"hooks\":' >.claude/settings.json" \
    "empties the hooks:echo '{\"hooks\":{\"SessionStart\":[]}}' >.claude/settings.json" \
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
# An init that overwrites a user's file and then fails leaves that file as it was.
mkdir -p .claude/hooks
echo "user file" >.claude/hooks/user.sh
printf '#!/bin/sh\necho liza >.claude/hooks/user.sh\nexit 1\n' >"$stub"
HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>"$clone/.git/partial.err"
partial_rc=$?
replaced_dir=$(sed -n 's/.* is kept in \(.*\)\/replaced\.$/\1/p' "$clone/.git/partial.err")
check "init that fails after overwriting a user file exits non-zero" test "$partial_rc" -ne 0
check "and puts the user file back" test "$(cat .claude/hooks/user.sh)" = "user file"
check "and keeps what it replaced, named" test "$(cat "$replaced_dir/replaced/.claude/hooks/user.sh" 2>/dev/null)" = liza
[ -n "$replaced_dir" ] && rm -rf -- "$replaced_dir"

# The same when init is interrupted (the whole process group, as Ctrl-C would be).
echo "user file" >.claude/hooks/user.sh
printf '#!/bin/sh\necho liza >.claude/hooks/user.sh\nsleep 30\n' >"$stub"
HOME="$stub_home" setsid "$shim" init --claude --yes </dev/null >/dev/null 2>"$clone/.git/interrupt.err" &
shim_pid=$!
for _ in $(seq 50); do
    [ "$(cat .claude/hooks/user.sh)" = liza ] && break
    sleep 0.1
done
kill -INT -- "-$shim_pid"
wait "$shim_pid"
interrupt_rc=$?
replaced_dir=$(sed -n 's/.* is kept in \(.*\)\/replaced\.$/\1/p' "$clone/.git/interrupt.err")
check "interrupted init exits non-zero" test "$interrupt_rc" -ne 0
check "and puts the user file back" test "$(cat .claude/hooks/user.sh)" = "user file"
check "and releases the lock and the committed settings" \
    test ! -e .claude/.liza-shim.lock -a ! -e .claude/settings.json.liza-shim-held
[ -n "$replaced_dir" ] && rm -rf -- "$replaced_dir"
rm -f .claude/hooks/user.sh && rmdir .claude/hooks
check "git status clean after the failures" test -z "$(git status --porcelain)"

# The pre-activation state, with a hook of the user's own, for the deactivation checks.
liza_dir=$(dirname "$shim")
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

# A clone activated before activation records existed gets a partial undo, said aloud.
check "re-activation succeeds" liza init --claude --yes
rm -f "$(git rev-parse --git-path liza)/activation.json"
bash "$liza_dir/deactivate.sh" 2>"$clone/.git/legacy.err"
check "legacy deactivate unlinks the contract" test ! -L CLAUDE.local.md
check "legacy deactivate removes Liza's hooks" test "$(jq --arg h "$HOME/.liza/" \
    '[.hooks[]?[]?.hooks[]?.command | select(contains($h) or test("\\.claude/hooks/"))] | length' \
    .claude/settings.local.json)" = 0
check "legacy deactivate keeps the user's hook" \
    jq -e '[.hooks.PreToolUse[]?.hooks[]?.command] | index("echo mine")' .claude/settings.local.json
check "legacy deactivate says what it left" grep -q permissions "$clone/.git/legacy.err"
check "activation succeeds after a legacy deactivate" liza init --claude --yes

# A record that can't be read: activation says so, and deactivation falls back.
echo '{' >"$(git rev-parse --git-path liza)/activation.json"
liza init --claude --yes </dev/null >/dev/null 2>"$clone/.git/corrupt.err"
check "activation over a corrupt record warns" grep -q "could not record" "$clone/.git/corrupt.err"
corrupt_kept=$(sed -n 's/.* kept as they were in \(.*\)\.$/\1/p' "$clone/.git/corrupt.err")
[ -n "$corrupt_kept" ] && rm -rf -- "$corrupt_kept"
check "deactivate over a corrupt record succeeds" bash "$liza_dir/deactivate.sh"
check "and unlinks the contract" test ! -L CLAUDE.local.md
check "activation succeeds after a corrupt-record deactivate" liza init --claude --yes

# rtk's hook lands in an activated clone once, and not again on re-activation. The stubs
# stand in for liza (a no-op init keeps the real hooks above) and for rtk.
printf '#!/bin/sh\n' >"$stub"
mkdir -p "$stub_home/.liza/bin"
printf '#!/bin/sh\n' >"$stub_home/.liza/bin/rtk"
chmod +x "$stub_home/.liza/bin/rtk"
rtk_hooks() {
    jq --arg c "$stub_home/.liza/bin/rtk hook claude" \
        '[.hooks.PreToolUse[]?.hooks[]? | select(.command == $c)] | length' .claude/settings.local.json
}
for run in first second; do
    HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>&1
    check "one rtk hook after the $run stubbed activation" test "$(rtk_hooks)" = 1
done

# Re-activations that change what Liza writes, in a fresh clone with a stub liza: the
# first adds an entry and sets a key, the second swaps the entry and sets the key again.
# Deactivation restores the original, neither the swapped-out entry nor the first value.
merge_clone="$stub_home/merge-clone"
git clone -q "$repo" "$merge_clone"
echo '{"permissions":{"allow":["mine"]},"model":"m0"}' >"$merge_clone/.claude/settings.local.json"
cp "$merge_clone/.claude/settings.local.json" "$merge_clone/.git/original.json"
cat >"$stub" <<'EOF'
#!/bin/sh
jq '.hooks.SessionStart = [{hooks: [{type: "command", command: "s"}]}]
    | .permissions.allow += ["liza-1"] | .model = "m1"' .claude/settings.json >.claude/t.json \
    && mv .claude/t.json .claude/settings.json
EOF
(cd "$merge_clone" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>&1)
cat >"$stub" <<'EOF'
#!/bin/sh
jq '.permissions.allow = (.permissions.allow - ["liza-1"] + ["liza-2"]) | .model = "m2"' \
    .claude/settings.json >.claude/t.json && mv .claude/t.json .claude/settings.json
EOF
(cd "$merge_clone" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>&1)
check "re-activations changed the settings" jq -e '.model == "m2"' "$merge_clone/.claude/settings.local.json"
(cd "$merge_clone" && HOME="$stub_home" bash "$liza_dir/deactivate.sh")
check "deactivate after changing re-activations restores the original" \
    test "$(jq -S . "$merge_clone/.claude/settings.local.json")" = "$(jq -S . "$merge_clone/.git/original.json")"

# An init that removes a user's file or replaces their symlink, with a stub liza:
# deactivate restores both.
gone_clone="$stub_home/gone-clone"
git clone -q "$repo" "$gone_clone"
mkdir -p "$gone_clone/.claude/hooks" "$gone_clone/.claude/links"
echo '{}' >"$gone_clone/.claude/settings.local.json"
echo "user file" >"$gone_clone/.claude/hooks/removed.sh"
ln -s /user/target "$gone_clone/.claude/links/linked.sh"
cat >"$stub" <<'EOF'
#!/bin/sh
rm -f .claude/hooks/removed.sh .claude/links/linked.sh
echo liza >.claude/links/linked.sh
echo liza >.claude/links/created.sh
jq '.hooks.SessionStart = [{hooks: [{type: "command", command: "s"}]}]' .claude/settings.json >.claude/t.json \
    && mv .claude/t.json .claude/settings.json
EOF
(cd "$gone_clone" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>&1)
check "the stub init removed the user's file" test ! -e "$gone_clone/.claude/hooks/removed.sh"
# A deactivate that fails part-way (here: the links directory is read-only, so restoring
# the symlink and removing the created file fail while the other restore succeeds) keeps
# the record, originals and exclude lines, and a rerun finishes without taking the
# already-restored file for an edit. Root ignores the permissions this relies on.
if [ "$(id -u)" != 0 ]; then
    gone_record="$(git -C "$gone_clone" rev-parse --absolute-git-dir)/liza"
    chmod a-w "$gone_clone/.claude/links"
    (cd "$gone_clone" && HOME="$stub_home" bash "$liza_dir/deactivate.sh" 2>/dev/null)
    failed_rc=$?
    chmod u+w "$gone_clone/.claude/links"
    check "a deactivate that can't restore fails" test "$failed_rc" -ne 0
    check "and keeps the record and originals for a rerun" \
        test -f "$gone_record/activation.json" -a -d "$gone_record/originals"
    check "and keeps the leftover file hidden" grep -qx /.claude/links/created.sh "$gone_clone/.git/info/exclude"
fi
check "deactivate (re)run succeeds" \
    bash -c "cd '$gone_clone' && HOME='$stub_home' bash '$liza_dir/deactivate.sh' 2>'$stub_home/rerun.err'"
check "the rerun takes no restored file for an edit" \
    test ! -e "$gone_clone/.claude/hooks/removed.sh.pre-liza" -a ! -s "$stub_home/rerun.err"
check "the rerun removes the created file and its exclude line" \
    bash -c "test ! -e '$gone_clone/.claude/links/created.sh' \
        && ! grep -qx /.claude/links/created.sh '$gone_clone/.git/info/exclude'"
check "deactivate restores a user file init removed" \
    test "$(cat "$gone_clone/.claude/hooks/removed.sh")" = "user file"
check "deactivate restores a user symlink init replaced" \
    test "$(readlink "$gone_clone/.claude/links/linked.sh")" = /user/target

# A backup that can't be made (an unreadable user file) stops init before it runs. The
# stub liza succeeds on its own, so only the refusal can fail this activation.
if [ "$(id -u)" != 0 ]; then
    refuse_clone="$stub_home/refuse-clone"
    git clone -q "$repo" "$refuse_clone"
    mkdir -p "$refuse_clone/.claude/hooks"
    echo '{}' >"$refuse_clone/.claude/settings.local.json"
    cat >"$stub" <<'EOF'
#!/bin/sh
jq '.hooks.SessionStart = [{hooks: [{type: "command", command: "s"}]}]' .claude/settings.json >.claude/t.json \
    && mv .claude/t.json .claude/settings.json
EOF
    echo "user file" >"$refuse_clone/.claude/hooks/unreadable.sh"
    chmod 000 "$refuse_clone/.claude/hooks/unreadable.sh"
    (cd "$refuse_clone" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>"$stub_home/refuse.err")
    refuse_rc=$?
    chmod 600 "$refuse_clone/.claude/hooks/unreadable.sh"
    check "init refuses when a backup fails" test "$refuse_rc" -ne 0
    check "and says nothing was changed" grep -q "could not back up" "$stub_home/refuse.err"
    check "and leaves the clone untouched" \
        test "$(cat "$refuse_clone/.claude/hooks/unreadable.sh")" = "user file" -a ! -L "$refuse_clone/CLAUDE.local.md"
fi

# Saving an original after init fails (read-only originals/), and later saving a .pre-liza
# copy fails: neither may lose the user's file. A stub liza overwrites .claude/keep/f.sh.
if [ "$(id -u)" != 0 ]; then
    cat >"$stub" <<'EOF'
#!/bin/sh
echo liza >.claude/keep/f.sh
jq '.hooks.SessionStart = [{hooks: [{type: "command", command: "s"}]}]' .claude/settings.json >.claude/t.json \
    && mv .claude/t.json .claude/settings.json
EOF
    for name in nosave preliza; do
        git clone -q "$repo" "$stub_home/$name-clone"
        mkdir -p "$stub_home/$name-clone/.claude/keep"
        echo '{}' >"$stub_home/$name-clone/.claude/settings.local.json"
        echo "user file" >"$stub_home/$name-clone/.claude/keep/f.sh"
    done

    nosave_clone="$stub_home/nosave-clone"
    mkdir -p "$nosave_clone/.git/liza/originals"
    chmod a-w "$nosave_clone/.git/liza/originals"
    (cd "$nosave_clone" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>"$stub_home/nosave.err")
    nosave_rc=$?
    chmod u+w "$nosave_clone/.git/liza/originals"
    kept_dir=$(sed -n 's/.*it is kept in \(.*\)\.$/\1/p' "$stub_home/nosave.err")
    check "activation that can't save an original fails" test "$nosave_rc" -ne 0
    check "and keeps the original where it says" test "$(cat "$kept_dir/.claude/keep/f.sh" 2>/dev/null)" = "user file"
    check "and doesn't record it as restorable" \
        test "$(jq '.overwritten | length' "$nosave_clone/.git/liza/activation.json")" = 0
    [ -n "$kept_dir" ] && rm -rf -- "$kept_dir"

    preliza_clone="$stub_home/preliza-clone"
    (cd "$preliza_clone" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>&1)
    echo "# edited" >>"$preliza_clone/.claude/keep/f.sh"
    chmod a-w "$preliza_clone/.claude/keep"
    (cd "$preliza_clone" && HOME="$stub_home" bash "$liza_dir/deactivate.sh" 2>/dev/null)
    preliza_rc=$?
    chmod u+w "$preliza_clone/.claude/keep"
    check "a deactivate that can't save a .pre-liza copy fails" test "$preliza_rc" -ne 0
    check "and keeps the original for a rerun" test -d "$preliza_clone/.git/liza/originals"
    (cd "$preliza_clone" && HOME="$stub_home" bash "$liza_dir/deactivate.sh" 2>/dev/null)
    check "the rerun saves the .pre-liza copy" \
        test "$(cat "$preliza_clone/.claude/keep/f.sh.pre-liza" 2>/dev/null)" = "user file"
fi

# An original saved before the record's write failed (a corrupt record here): deactivate
# puts it beside the file instead of dropping it with the rest of the record.
orphan_clone="$stub_home/orphan-clone"
git clone -q "$repo" "$orphan_clone"
mkdir -p "$orphan_clone/.claude/keep" "$orphan_clone/.git/liza"
echo '{}' >"$orphan_clone/.claude/settings.local.json"
echo "user file" >"$orphan_clone/.claude/keep/f.sh"
echo '{' >"$orphan_clone/.git/liza/activation.json"
cat >"$stub" <<'EOF'
#!/bin/sh
echo liza >.claude/keep/f.sh
jq '.hooks.SessionStart = [{hooks: [{type: "command", command: "s"}]}]' .claude/settings.json >.claude/t.json \
    && mv .claude/t.json .claude/settings.json
EOF
(cd "$orphan_clone" && HOME="$stub_home" "$shim" init --claude --yes </dev/null >/dev/null 2>"$stub_home/orphan.err")
orphan_kept=$(sed -n 's/.* kept as they were in \(.*\)\.$/\1/p' "$stub_home/orphan.err")
[ -n "$orphan_kept" ] && rm -rf -- "$orphan_kept"
(cd "$orphan_clone" && HOME="$stub_home" bash "$liza_dir/deactivate.sh" 2>"$stub_home/orphan-deactivate.err")
check "deactivate saves an unrecorded original beside its file" \
    test "$(cat "$orphan_clone/.claude/keep/f.sh.pre-liza" 2>/dev/null)" = "user file"
check "and names it" grep -q -F -- "f.sh.pre-liza" "$stub_home/orphan-deactivate.err"

# --tools undoes the toolchain's changes, and only with --tools. A stub claude logs its
# calls; a stub ~/.claude.json holds the codebase-memory-mcp switch-off.
tools_home="$stub_home/tools"
mkdir -p "$tools_home/bin"
cat >"$tools_home/bin/claude" <<EOF
#!/bin/sh
echo "\$*" >>"$tools_home/claude-calls"
EOF
chmod +x "$tools_home/bin/claude"
jq -n --arg p "$clone" '{projects: {($p): {disabledMcpServers: ["other", "codebase-memory-mcp"]}}}' \
    >"$tools_home/.claude.json"
cp .claude/settings.local.json "$clone/.git/before-tools.json"
HOME="$tools_home" PATH="$tools_home/bin:$PATH" bash "$liza_dir/deactivate.sh" --tools
check "--tools removes context7" grep -qx "mcp remove --scope local context7" "$tools_home/claude-calls"
check "--tools re-enables codebase-memory-mcp" \
    test "$(jq -c --arg p "$clone" '.projects[$p].disabledMcpServers' "$tools_home/.claude.json")" = '["other"]'
check "--tools leaves the settings alone" cmp -s .claude/settings.local.json "$clone/.git/before-tools.json"
rm -f "$tools_home/claude-calls"

mkdir .claude/.liza-shim.lock
bash "$liza_dir/deactivate.sh" 2>/dev/null
lock_rc=$?
rmdir .claude/.liza-shim.lock
check "deactivate refuses while an init holds the lock" test "$lock_rc" -ne 0

PATH="$tools_home/bin:$PATH" bash "$liza_dir/deactivate.sh"
check "plain deactivate leaves the toolchain alone" test ! -e "$tools_home/claude-calls"

exit $((failures > 0))
