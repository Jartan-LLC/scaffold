#!/bin/bash
#
# postAttachCommand — runs each time a client attaches to the container.
# Refreshes this project's Claude Code plugins, and the marketplaces they come from, so
# the newest versions load on the next session. Best-effort: every step swallows errors so
# a network hiccup never blocks attaching.

command -v claude &>/dev/null && command -v node &>/dev/null || exit 0
project=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# The claude-data volume holds every project's installs; update only user-scope plugins and
# this project's. One "id scope" line per plugin.
plugins=$(claude plugins list --json 2>/dev/null | PROJECT="$project" node -e '
let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  let plugins = [];
  try { plugins = JSON.parse(input); } catch (e) {}
  if (!Array.isArray(plugins)) plugins = [];
  for (const p of plugins) {
    if (p && p.id && (p.scope === "user" || p.projectPath === process.env.PROJECT)) {
      console.log(p.id, p.scope);
    }
  }
});
')

for marketplace in $(printf '%s\n' "$plugins" | sed -n 's/^[^@ ]*@\([^ ]*\) .*/\1/p' | sort -u); do
    claude plugins marketplace update "$marketplace" 2>/dev/null || true
done
while read -r plugin_id scope; do
    [ -n "$plugin_id" ] || continue
    claude plugins update "$plugin_id" --scope "$scope" 2>/dev/null || true
done <<<"$plugins"
