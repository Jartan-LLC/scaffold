#!/bin/bash
#
# postAttachCommand — runs each time a client attaches to the container.
# Refreshes Claude Code marketplaces AND installed plugins so the newest
# versions are picked up on the next session. Best-effort: every step swallows
# errors so a network hiccup never blocks attaching.

# Refresh marketplace metadata first so plugin updates resolve to the latest
# available versions.
claude plugins marketplace update 2>/dev/null || true

# `claude plugins update` acts on one plugin at a time and has no bulk form, so
# enumerate installed plugins (id + scope) and update each within its own scope.
# node ships with the claude CLI, so use it to parse the JSON listing.
if command -v claude &>/dev/null && command -v node &>/dev/null; then
    claude plugins list --json 2>/dev/null | node -e '
let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  let plugins = [];
  try { plugins = JSON.parse(input); } catch (e) {}
  for (const p of plugins) {
    if (p && p.id) console.log(p.id, p.scope || "user");
  }
});
' | while read -r plugin_id scope; do
        [ -n "$plugin_id" ] || continue
        claude plugins update "$plugin_id" --scope "$scope" 2>/dev/null || true
    done
fi
