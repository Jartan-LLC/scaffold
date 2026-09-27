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

# --- --tools: undo the toolchain's changes to Claude Code, and nothing else ---
if [ "${1:-}" = --tools ]; then
    command -v claude >/dev/null || finish
    # Keyed like tools.sh, by the directory post-create runs in. ~/.claude.json is a
    # symlink into the claude-data volume: edit its target, atomically.
    claude_json=$(readlink -f "$HOME/.claude.json")
    # tools.sh registers context7 at local scope only; one at another scope is the user's.
    if jq -e --arg p "$top" '.projects[$p].mcpServers.context7' "$claude_json" >/dev/null 2>&1; then
        claude mcp remove --scope local context7 >/dev/null || failed+=("context7 removal")
    fi
    if jq -e --arg p "$top" '.projects[$p].disabledMcpServers // [] | index("codebase-memory-mcp")' \
        "$claude_json" >/dev/null 2>&1; then
        if ! { jq --arg p "$top" '.projects[$p].disabledMcpServers -= ["codebase-memory-mcp"]' \
            "$claude_json" >"$claude_json.tmp" && mv "$claude_json.tmp" "$claude_json"; }; then
            rm -f "$claude_json.tmp"
            failed+=("codebase-memory-mcp re-enable")
        fi
    fi
    finish
fi

# --- Undo activation, from its record ---
local_settings=.claude/settings.local.json
core_contract="$HOME/.liza/CORE.md"
record_dir=$(git_path "$top" liza)
record="$record_dir/activation.json"
exclude_file=$(git_path "$top" info/exclude)

# Originals without a record or link: an activation interrupted before either was made.
if [ ! -f "$record" ] && [ ! -d "$record_dir/originals" ] \
    && [ "$(readlink CLAUDE.local.md)" != "$core_contract" ]; then
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
if ! jq -e . "$record" >/dev/null 2>&1; then
    # No readable record: only the contract link and any saved originals can be undone.
    echo "deactivate: no readable activation record, so Liza's settings entries and files" \
        "were left; check $local_settings and $exclude_file." >&2
else
    # Liza's settings entries go; entries the user added or changed since stay.
    if [ -f "$local_settings" ]; then
        if ! { jq -L "$here" --slurpfile rec "$record" 'include "activation-record"; revert($rec[0].settings)' \
            "$local_settings" >"$local_settings.tmp" && mv "$local_settings.tmp" "$local_settings"; }; then
            rm -f "$local_settings.tmp"
            failed+=("settings revert")
        fi
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
        # Already restored by an earlier, failed run: the two fingerprints (minus their
        # differing paths) match.
        [ -n "$now" ] && [ "${now#"$path" }" = "${restored#"$original" }" ] && continue
        if [ "${now:-"$path absent"}" = "$entry" ]; then
            put_copy "$original" "$path" || failed+=("restoring $path")
        else
            if cp -P -p "$original" "$path.pre-liza"; then
                kept+=("$path (original in $path.pre-liza)")
            else
                failed+=("saving $path.pre-liza")
            fi
        fi
    done
    # A file activation created goes, unless it was edited since.
    mapfile -t recorded < <(jq -r '.files[] | "\(.path) \(.fp)"' "$record")
    for entry in "${recorded[@]}"; do
        path=${entry% *}
        now=$(fingerprint "$path")
        [ -n "$now" ] || continue
        if [ "$now" = "$entry" ]; then remove_created "$path"; else kept+=("$path"); fi
    done
    # Liza's own exclude lines name files its tools generate after activation, which go,
    # edits included; one that existed before activation stays.
    mapfile -t drop_lines < <(jq -r '.exclude_lines[]' "$record")
    mapfile -t preexisting < <(jq -r '(.preexisting // [])[]' "$record")
    for line in "${drop_lines[@]}"; do
        [[ "$line" == *[*?[]* ]] && continue
        path="$top/${line#/}"
        printf '%s\n' "${recorded[@]}" | grep -q -F -- "$path " && continue
        printf '%s\n' "${preexisting[@]}" | grep -q -x -F -- "$path" && continue
        # The shim only saw the top level and .claude/ before init: elsewhere, the file may
        # be the user's.
        if [[ "${line#/}" == */* && "${line#/}" != .claude/* ]]; then
            [ -f "$path" ] && kept+=("$path")
            continue
        fi
        [ -f "$path" ] && remove_created "$path"
    done
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

# --- Clean up: what is left for the user, the contract link, emptied settings and dirs ---
[ ${#kept[@]} -eq 0 ] || echo "deactivate: left these for you to check: ${kept[*]}" >&2
if [ -f "$local_settings" ] && [ "$(jq -c . "$local_settings" 2>/dev/null)" = "{}" ]; then
    rm -f "$local_settings"
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
