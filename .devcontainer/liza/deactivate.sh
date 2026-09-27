#!/bin/bash
# Undoes activate.sh's activation in this clone, from the record the shim keeps: the
# settings entries and files activation added (a file edited since is kept and named),
# its exclude lines and the contract link. --tools instead undoes the toolchain's changes
# to Claude Code: the context7 registration and the codebase-memory-mcp switch-off.
# ~/.liza stays: it's this project's volume, and rebuilding with the switches off stops
# using it.

set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=.devcontainer/liza/activation-lib.sh
source "$here/activation-lib.sh"
top=$(git rev-parse --show-toplevel) || exit 1
cd "$top" || exit 1
failed=()

finish() {
    if [ ${#failed[@]} -gt 0 ]; then
        echo "Warning: Liza deactivation failed: ${failed[*]}" >&2
        exit 1
    fi
    exit 0
}

# Remove a file activation created, unless the project has since started tracking it. A
# failed removal is recorded, so the record survives for a rerun.
remove_created() {
    git ls-files --error-unmatch -- "$1" >/dev/null 2>&1 && return 0
    rm -f -- "$1" || { failed+=("removing $1"); return 1; }
}

if [ "${1:-}" = --tools ]; then
    command -v claude >/dev/null || finish
    if claude mcp get context7 >/dev/null 2>&1; then
        claude mcp remove --scope local context7 >/dev/null || failed+=("context7 removal")
    fi
    # Keyed like tools.sh, by the directory post-create runs in. ~/.claude.json is a
    # symlink into the claude-data volume: edit its target, atomically.
    claude_json=$(readlink -f "$HOME/.claude.json")
    if jq -e --arg p "$top" '.projects[$p].disabledMcpServers // [] | index("codebase-memory-mcp")' \
        "$claude_json" >/dev/null 2>&1; then
        jq --arg p "$top" '.projects[$p].disabledMcpServers -= ["codebase-memory-mcp"]' \
            "$claude_json" >"$claude_json.tmp" \
            && mv "$claude_json.tmp" "$claude_json" \
            || failed+=("codebase-memory-mcp re-enable")
    fi
    finish
fi

settings=.claude/settings.local.json
liza_home="$HOME/.liza/"
core_contract="$HOME/.liza/CORE.md"
record_dir=$(git_path "$top" liza)
record="$record_dir/activation.json"
exclude_file=$(git_path "$top" info/exclude)
hooks_dir=$(git_path "$top" hooks)

if [ ! -f "$record" ] && [ "$(readlink CLAUDE.local.md)" != "$core_contract" ] \
    && ! jq -e -L "$here" --arg h "$liza_home" 'include "activation-record"; has_liza_hooks($h)' \
        "$settings" >/dev/null 2>&1; then
    finish  # never activated
fi

lock=.claude/.liza-shim.lock
if ! mkdir -p .claude || ! mkdir "$lock" 2>/dev/null; then
    echo "deactivate: $lock is held by a running liza init; remove it if none is running." >&2
    exit 1
fi
trap 'rmdir "$lock"' EXIT

drop_lines=()  # exclude lines to remove
kept=()        # files left for the user to check, with where their original is
accounted=()   # originals the record lists
# A record that can't be read undoes like one that was never written. One marked legacy
# came from re-activating a clone activated before records existed: undo it, then fall back.
record_ok=false legacy=true
if recorded_legacy=$(jq -r '.legacy' "$record" 2>/dev/null); then
    record_ok=true legacy=$recorded_legacy
fi
if $record_ok; then
    if [ -f "$settings" ]; then
        jq -L "$here" --slurpfile rec "$record" 'include "activation-record"; revert($rec[0].settings)' \
            "$settings" >"$settings.tmp" && mv "$settings.tmp" "$settings" || failed+=("settings revert")
    fi
    # A user file init overwrote or removed gets its original back, unless Liza's version
    # was edited since; then the original goes beside it.
    mapfile -t overwritten < <(jq -r '(.overwritten // [])[] | "\(.path) \(.fp)"' "$record")
    for entry in "${overwritten[@]}"; do
        path=${entry% *}
        original="$record_dir/originals/${path#"$top"/}"
        [ -e "$original" ] || [ -L "$original" ] || continue
        accounted+=("$original")
        now=$(fingerprint "$path")
        restored=$(fingerprint "$original")
        [ -n "$now" ] && [ "${now#"$path" }" = "${restored#"$original" }" ] && continue  # a rerun
        if [ "${now:-"$path absent"}" = "$entry" ]; then
            rm -f -- "$path"
            cp -P -p "$original" "$path" || failed+=("restoring $path")
        else
            if cp -P -p "$original" "$path.pre-liza"; then
                kept+=("$path (original in $path.pre-liza)")
            else
                failed+=("saving $path.pre-liza")
            fi
        fi
    done
    mapfile -t recorded < <(jq -r '.files[] | "\(.path) \(.fp)"' "$record")
    for entry in "${recorded[@]}"; do
        path=${entry% *}
        now=$(fingerprint "$path")
        [ -n "$now" ] || continue
        if [ "$now" = "$entry" ]; then remove_created "$path"; else kept+=("$path"); fi
    done
    # Liza's own exclude lines name files its tools generate after activation.
    mapfile -t drop_lines < <(jq -r '.exclude_lines[]' "$record")
    for line in "${drop_lines[@]}"; do
        [[ "$line" == *[*?[]* ]] && continue
        path="$top/${line#/}"
        printf '%s\n' "${recorded[@]}" | grep -q -F -- "$path " && continue
        [ -f "$path" ] && remove_created "$path"
    done
fi
if [ "$legacy" = true ]; then
    # Liza's settings from before the record can't be told from the user's, so remove only
    # what is recognizably Liza's and say what was left.
    if [ -f "$settings" ]; then
        mapfile -t hook_scripts < <(jq -r -L "$here" --arg h "$liza_home" \
            'include "activation-record"; liza_hook_scripts($h)[]' "$settings")
        jq -L "$here" --arg h "$liza_home" 'include "activation-record"; drop_liza_hooks($h)' \
            "$settings" >"$settings.tmp" && mv "$settings.tmp" "$settings" || failed+=("legacy hook removal")
        for script in "${hook_scripts[@]}"; do
            remove_created "$top/$script" && drop_lines+=("/$script")
        done
    fi
    for link in .claude/skills/*; do
        [ -L "$link" ] && [[ "$(readlink "$link")" == "$liza_home"* ]] || continue
        remove_created "$link" && drop_lines+=("/$link")
    done
    for hook in "$hooks_dir"/*; do
        [[ "${hook##*/}" == liza-index* ]] || [ "$(readlink "$hook")" = liza-index-hook.sh ] || continue
        remove_created "$hook"
    done
    remove_created "$(git rev-parse --absolute-git-dir)/liza-provider-activations.json"
    echo "deactivate: this clone's activation wasn't recorded, so Liza's permissions and its" \
        "own lines in $exclude_file were left; check them and $settings." >&2
fi

# An original the record doesn't list (the record's write failed after it was saved) is the
# user's only copy of that file: put it beside the file rather than drop it.
if [ -d "$record_dir/originals" ]; then
    while IFS= read -r -d '' original; do
        printf '%s\n' "${accounted[@]}" | grep -q -x -F -- "$original" && continue
        path="$top/${original#"$record_dir/originals/"}"
        if [ -e "$path.pre-liza" ] || [ -L "$path.pre-liza" ] \
            || { mkdir -p "$(dirname "$path")" && cp -P -p "$original" "$path.pre-liza"; }; then
            kept+=("$path (original in $path.pre-liza)")
        else
            failed+=("saving $path.pre-liza")
        fi
    done < <(find "$record_dir/originals" \( -type f -o -type l \) -print0)
fi

[ ${#kept[@]} -eq 0 ] || echo "deactivate: left these for you to check: ${kept[*]}" >&2
if [ -f "$settings" ] && [ "$(jq -c . "$settings" 2>/dev/null)" = "{}" ]; then
    rm -f "$settings"
fi
[ "$(readlink CLAUDE.local.md)" = "$core_contract" ] && remove_created CLAUDE.local.md
rmdir .claude/hooks .claude/skills 2>/dev/null

# After a failure the exclude lines stay too, so what's left stays hidden until a rerun.
if [ ${#failed[@]} -eq 0 ] && [ -f "$exclude_file" ] && [ ${#drop_lines[@]} -gt 0 ]; then
    grep -v -x -F -f <(printf '%s\n' "${drop_lines[@]}") "$exclude_file" >"$exclude_file.tmp"
    mv "$exclude_file.tmp" "$exclude_file" || failed+=("exclude cleanup")
fi
# Only a complete undo drops the record and the originals; after a failure they stay, and
# a rerun picks up where this one stopped.
if [ ${#failed[@]} -eq 0 ]; then
    rm -f -- "$record" "$record.tmp"
    rm -rf -- "${record_dir:?}/originals"
    rmdir "$record_dir" 2>/dev/null
fi
finish
