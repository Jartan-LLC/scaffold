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
    echo "liza shim: $held_settings exists from an interrupted init; move it back to settings.json first." >&2
    exit 1
fi

had_global_contract=false
[ -e "$global_contract" ] || [ -L "$global_contract" ] && had_global_contract=true
untracked_before=$(git -C "$top" ls-files --others --exclude-standard)

# Liza always merges into .claude/settings.json. Putting the local file in its place for
# the run lets Liza's own merge write the local file, and the committed one is never opened.
restore_settings() {
    [ -f "$shared_settings" ] && mv -f "$shared_settings" "$local_settings"
    [ -f "$held_settings" ] && mv -f "$held_settings" "$shared_settings"
}
release() {
    restore_settings
    rmdir "$lock"
}
[ -f "$shared_settings" ] && mv "$shared_settings" "$held_settings"
[ -f "$local_settings" ] && mv "$local_settings" "$shared_settings"
trap release EXIT
trap 'exit 130' INT TERM

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
[ "$rc" -eq 0 ] || exit "$rc"

# rtk's own `rtk init -g` writes this hook to ~/.claude/settings.json, rewriting commands
# in every project; here it applies to activated clones only.
rtk="$HOME/.liza/bin/rtk"
if [ -x "$rtk" ] && [ -f "$local_settings" ]; then
    jq --arg cmd "$rtk hook claude" '
        .hooks.PreToolUse //= []
        | if any(.hooks.PreToolUse[].hooks[]?; .command == $cmd) then .
          else .hooks.PreToolUse += [{matcher: "Bash", hooks: [{type: "command", command: $cmd}]}] end
    ' "$local_settings" >"$local_settings.tmp" && mv "$local_settings.tmp" "$local_settings"
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
exclude_file=$(git -C "$top" rev-parse --git-path info/exclude)
[[ "$exclude_file" == /* ]] || exclude_file="$top/$exclude_file"
comm -13 <(sort <<<"$untracked_before") <(git -C "$top" ls-files --others --exclude-standard | sort) \
    | sed 's|^|/|' >>"$exclude_file"

exit $rc
