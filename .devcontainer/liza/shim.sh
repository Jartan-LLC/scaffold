#!/bin/bash
# `liza` on PATH. Every subcommand goes to the real binary; `init` is wrapped so Liza's
# activation lands in this clone's local-scope files instead of the committed
# .claude/settings.json and the user-wide ~/.claude/CLAUDE.md. Upstream tracking this:
# liza-mas/liza issue 164.

set -uo pipefail

real_liza="$HOME/.liza/libexec/liza"

# Global flags can precede the subcommand; -C/--project-root and --update-channel take a value.
subcommand="" project_root=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    case "${args[i]}" in
        -C | --project-root) project_root="${args[i + 1]:-}"; ((i++)) ;;
        --project-root=*) project_root="${args[i]#*=}" ;;
        --update-channel) ((i++)) ;;
        -*) ;;
        *) subcommand="${args[i]}"; break ;;
    esac
done
[ "$subcommand" = init ] || exec "$real_liza" "$@"

top=$(git -C "${project_root:-.}" rev-parse --show-toplevel) || exit 1
claude_dir="$top/.claude"
shared_settings="$claude_dir/settings.json"
local_settings="$claude_dir/settings.local.json"
held_settings="$claude_dir/settings.json.liza-shim-held"
backup_settings="$claude_dir/settings.local.json.liza-shim-backup"
global_contract="$HOME/.claude/CLAUDE.md"
core_contract="$HOME/.liza/CORE.md"

mkdir -p "$claude_dir"
# mkdir is atomic: a second concurrent init would otherwise swap the already-swapped files.
lock="$claude_dir/.liza-shim.lock"
if ! mkdir "$lock" 2>/dev/null; then
    echo "liza shim: another init holds $lock; remove it if none is running." >&2
    exit 1
fi
if [ -e "$held_settings" ]; then
    rmdir "$lock"
    echo "liza shim: $held_settings exists from an interrupted init; move it back to settings.json" \
        "(and any settings.local.json.liza-shim-backup back to settings.local.json) first." >&2
    exit 1
fi

had_global_contract=false
if [ -e "$global_contract" ] || [ -L "$global_contract" ]; then had_global_contract=true; fi
untracked_before=$(git -C "$top" ls-files --others --exclude-standard)

# Snapshots for the activation record written at the end.
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=.devcontainer/liza/activation-lib.sh
source "$here/activation-lib.sh"
git_dir=$(git -C "$top" rev-parse --absolute-git-dir)
hooks_dir=$(git_path "$top" hooks)
exclude_file=$(git_path "$top" info/exclude)
record_dir=$(git_path "$top" liza)
record="$record_dir/activation.json"
recorded_files=()
[ -f "$record" ] && mapfile -t recorded_files < <(jq -r '.files[].path' "$record" 2>/dev/null)
recorded_before=$(fingerprint "${recorded_files[@]}")
git_before=$(fingerprint "$git_dir"/liza* "$hooks_dir"/*)
exclude_before=$(cat "$exclude_file" 2>/dev/null)
pre_settings=$(cat "$local_settings" 2>/dev/null || echo '{}')
# --- Back up the user's files init may clobber ---
# Liza's init overwrites or removes an untracked file of the user's at a path it writes
# to. Each such candidate (file or symlink) is copied to originals/ first, and the copy
# stays only if init changes the file. Liza's own files are skipped, and so is a file an
# earlier activation already saved: that first copy is the user's.
originals="$record_dir/originals"
mapfile -t saved < <(jq -r '(.overwritten // [])[].path' "$record" 2>/dev/null)
mapfile -t candidates < <({
    git -C "$top" ls-files --others -- .claude ':(glob)*'
    git -C "$top" ls-files --others --ignored --exclude-standard -- .claude ':(glob)*'
} | sort -u | grep -v -x -F -e .claude/settings.local.json -e .claude/settings.json | sed "s|^|$top/|")

# Drops the copies of candidates other than the paths given.
prune_originals() {  # paths to keep...
    local path
    for path in "${!fp_before[@]}"; do
        printf '%s\n' "$@" | grep -q -x -F -- "$path" || rm -f -- "$originals/${path#"$top"/}"
    done
    find "$record_dir" -depth -type d -empty -delete 2>/dev/null
}

declare -A fp_before=()
for path in "${candidates[@]}"; do
    printf '%s\n' "${recorded_files[@]}" "${saved[@]}" | grep -q -x -F -- "$path" && continue
    fp=$(fingerprint "$path")
    [ -n "$fp" ] || continue
    fp_before[$path]=$fp
    # Without this copy, init could destroy the file for good: stop before it runs.
    if ! { mkdir -p "$(dirname "$originals/${path#"$top"/}")" && cp -P -p "$path" "$originals/${path#"$top"/}"; }; then
        prune_originals
        rmdir "$lock"
        echo "liza shim: could not back up $path before init; nothing was changed." >&2
        exit 1
    fi
done

# A failed or interrupted init is undone for the user's files too: each candidate it changed
# goes back from originals/. What it replaces could be init's write or the user's own edit
# made during init, which can't be told apart, so that is set aside in replaced/.
restore_candidates() {
    local path rel replaced=false kept=()
    for path in "${!fp_before[@]}"; do
        [ "$(fingerprint "$path")" = "${fp_before[$path]}" ] && continue
        rel=${path#"$top"/}
        if [ -e "$path" ] || [ -L "$path" ]; then
            if ! { mkdir -p "$(dirname "$record_dir/replaced/$rel")" && cp -P -p "$path" "$record_dir/replaced/$rel"; }; then
                kept+=("$path")
                echo "liza shim: left $path as the failed init left it; its original is in $originals." >&2
                continue
            fi
            replaced=true
        fi
        rm -f -- "$path"
        cp -P -p "$originals/$rel" "$path" && continue
        kept+=("$path")
        echo "liza shim: could not restore $path after the failed init; its original is in $originals." >&2
    done
    $replaced && echo "liza shim: restored the files the failed init changed; what it replaced is in $record_dir/replaced." >&2
    prune_originals "${kept[@]}"
}

# Liza always merges into .claude/settings.json. Putting the local file in its place for
# the run lets Liza's own merge write the local file, and the committed one is never opened.
restore_settings() {
    [ -f "$shared_settings" ] && mv -f "$shared_settings" "$local_settings"
    [ -f "$held_settings" ] && mv -f "$held_settings" "$shared_settings"
}
# Liza writes settings non-atomically and only warns when the merge fails, so the result
# is kept only if it parses and carries Liza's hooks; otherwise the backup, the one copy
# of the untracked local settings, goes back.
init_ok=true
release() {
    restore_settings
    if ! jq -e '.hooks.SessionStart | length > 0' "$local_settings" >/dev/null 2>&1; then
        init_ok=false
        if [ -f "$backup_settings" ]; then
            mv -f "$backup_settings" "$local_settings"
        else
            rm -f "$local_settings"
        fi
    fi
    rm -f "$backup_settings"
    rmdir "$lock"
}
[ -f "$local_settings" ] && cp -p "$local_settings" "$backup_settings"
[ -f "$shared_settings" ] && mv "$shared_settings" "$held_settings"
[ -f "$local_settings" ] && mv "$local_settings" "$shared_settings"
trap 'release; restore_candidates' EXIT
trap 'exit 130' INT TERM

# --- Run Liza's init ---

# Liza reads the toolchain's LIZA_ENABLE_* gates at init time, and the shell running init
# (a script, /onboard, Liza's operator agent) may not have loaded them.
if [ "${INSTALL_LIZA_TOOLS:-false}" = true ] && [ -f "$HOME/.liza/toolchain/env.sh" ]; then
    # shellcheck source=/dev/null
    source "$HOME/.liza/toolchain/env.sh"
fi

"$real_liza" "$@"
rc=$?

release
trap - EXIT
if [ "$rc" -ne 0 ]; then
    restore_candidates
    exit "$rc"
fi
if ! $init_ok; then
    restore_candidates
    echo "liza shim: init left no valid Liza hooks in settings.local.json; restored it and linked nothing." >&2
    exit 1
fi

# --- Finish activation locally ---
# rtk's own `rtk init -g` writes this hook to ~/.claude/settings.json, rewriting commands
# in every project; here it applies to activated clones only.
rtk="$HOME/.liza/bin/rtk"
if [ -x "$rtk" ] && [ -f "$local_settings" ]; then
    if ! { jq --arg cmd "$rtk hook claude" '
        .hooks.PreToolUse //= []
        | if any(.hooks.PreToolUse[].hooks[]?; .command == $cmd) then .
          else .hooks.PreToolUse += [{matcher: "Bash", hooks: [{type: "command", command: $cmd}]}] end
    ' "$local_settings" >"$local_settings.tmp" && mv "$local_settings.tmp" "$local_settings"; }; then
        rm -f "$local_settings.tmp"
        echo "liza shim: could not add rtk's hook to $local_settings" >&2
    fi
fi

# `--claude` points ~/.claude/CLAUDE.md at the contract when that path is free, which
# loads the contract in every project sharing ~/.claude. Keep it in this clone instead.
if ! $had_global_contract && [ "$(readlink "$global_contract")" = "$core_contract" ]; then
    rm -- "$global_contract"
fi
# A symlink, not an @import: imports outside the project are skipped in `claude -p`
# sessions, and a worktree session skips an ancestor CLAUDE.local.md's imports.
contract="$top/CLAUDE.local.md"
if [ -L "$contract" ] || [ ! -e "$contract" ]; then
    ln -sfn "$core_contract" "$contract"
else
    echo "Warning: $contract is your own file, so Liza's contract was not linked there." >&2
fi

for skill_md in "$HOME"/.liza/skills/*/SKILL.md; do
    [ -e "$skill_md" ] || continue
    skill_dir=${skill_md%/SKILL.md}
    link="$claude_dir/skills/${skill_dir##*/}"
    if [ -L "$link" ] || [ ! -e "$link" ]; then
        mkdir -p "$claude_dir/skills"
        ln -sfn "$skill_dir" "$link"
    fi
done

# Whatever init just created that git would show (hooks, .claudeignore, skill links) is
# this clone's activation, not project content: exclude it locally.
mapfile -t created < <(comm -13 <(sort <<<"$untracked_before") \
    <(git -C "$top" ls-files --others --exclude-standard | sort) | sed "s|^|$top/|")
for path in "${created[@]}"; do
    echo "/${path#"$top"/}"
done >>"$exclude_file"

# --- Record what this activation changed, so deactivate.sh undoes exactly that ---
# Candidates init changed keep their copy in originals/ and are recorded as overwritten,
# with the fingerprint of Liza's version ("absent" if init removed the file).
overwritten=() keep=("${saved[@]}")
for path in "${!fp_before[@]}"; do
    now=$(fingerprint "$path")
    now=${now:-"$path absent"}
    [ "$now" != "${fp_before[$path]}" ] || continue
    overwritten+=("$now") keep+=("$path")
done
prune_originals "${keep[@]}"

# Each fingerprint list is "<path> <fingerprint>" lines, taken before and after init:
# files already recorded (a later init may rewrite them), new worktree files, and the git
# dir's hooks and liza* files. activation-record.jq folds them into the record.
mkdir -p "$record_dir"
[ -f "$record" ] || echo '{"settings": [], "files": [], "overwritten": [], "exclude_lines": []}' >"$record"
if ! { jq -L "$here" --slurpfile pre <(printf '%s' "$pre_settings") --slurpfile post "$local_settings" \
        --arg created "$(fingerprint "${created[@]}")" \
        --arg recorded_before "$recorded_before" --arg recorded_after "$(fingerprint "${recorded_files[@]}")" \
        --arg git_before "$git_before" --arg git_after "$(fingerprint "$git_dir"/liza* "$hooks_dir"/*)" \
        --arg overwritten "$(printf '%s\n' "${overwritten[@]}")" \
        --arg exclude_added "$(comm -13 <(sort -u <<<"$exclude_before") <(sort -u "$exclude_file"))" '
        include "activation-record";
        record_activation($pre[0]; $post[0]; $created; $recorded_before; $recorded_after;
                          $git_before; $git_after; $overwritten; $exclude_added)
    ' "$record" >"$record.tmp" && mv "$record.tmp" "$record"; }; then
    rm -f "$record.tmp"
    echo "liza shim: could not record this activation; deactivate.sh will only partly undo it." \
        "Originals of files init overwrote are in $originals." >&2
    exit 1
fi
