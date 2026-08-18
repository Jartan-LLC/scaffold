#!/bin/bash
#
# postAttachCommand — runs each time a client attaches to the container.
# Reconciles the plugins .claude/settings.json declares against the shared
# ~/.claude volume, then refreshes marketplaces and installed plugins.
# Best-effort: every step swallows errors, so a network hiccup never blocks
# attaching and one plugin's failure never stops the rest.

command -v claude &>/dev/null || exit 0
# node ships with the claude CLI; used here to parse the JSON listings.
command -v node &>/dev/null || exit 0

project_dir="$PWD"
settings=".claude/settings.json"

# `claude plugins` reformats settings.json and appends transitive dependencies
# to enabledPlugins. That file is tracked and this hook is unattended, so
# snapshot it and put it back. The --scope local installs below record the same
# enablement in the gitignored settings.local.json, so nothing is lost.
settings_existed=false
snapshot=""
if [ -f "$settings" ]; then
    settings_existed=true
    # No snapshot means no way to put the file back, so do nothing at all rather
    # than reformat a tracked file with no way to undo it.
    snapshot="$(mktemp 2>/dev/null)" && cp "$settings" "$snapshot" || exit 0
fi

restore_settings() {
    if [ "$settings_existed" = true ]; then
        if [ -n "$snapshot" ] && [ -f "$settings" ] && ! cmp -s "$snapshot" "$settings"; then
            cp "$snapshot" "$settings"
        fi
    elif [ -f "$settings" ]; then
        rm -f "$settings" # absent when we started, so this hook created it
    fi
    [ -n "$snapshot" ] && rm -f "$snapshot"
}
trap restore_settings EXIT

# Declared state, from the tracked settings.json alone. settings.local.json is
# the install *record* this hook writes, not a policy source: merging it back in
# would let the first attach's record outlive the declaration, so removing a
# plugin from the tracked file could never take it away again.
# Mode "marketplaces" emits "<name>\t<add-argument>"; "plugins" emits ids.
read_declared() {
    node -e '
const fs = require("fs");
const [main, mode] = process.argv.slice(1);
const load = (p) => {
  try {
    const v = JSON.parse(fs.readFileSync(p, "utf8"));
    return v && typeof v === "object" ? v : {};
  } catch (e) { return {}; }
};
const declared = (key) => Object.assign({}, load(main)[key]);
if (mode === "marketplaces") {
  for (const [name, entry] of Object.entries(declared("extraKnownMarketplaces"))) {
    const s = entry && entry.source;
    if (!s || typeof s !== "object") continue;
    // No --ref flag exists, but "add" parses a ref off the source and records
    // it. Dropping the declared ref would silently unpin the marketplace.
    let arg = null;
    if (s.source === "github" && s.repo) arg = s.ref ? s.repo + "@" + s.ref : s.repo;
    else if (s.url) arg = s.ref ? s.url + "#" + s.ref : s.url;
    else if (s.path) arg = s.path;
    if (arg && !/\s/.test(name) && !/\s/.test(arg)) console.log(name + "\t" + arg);
  }
} else {
  for (const [id, enabled] of Object.entries(declared("enabledPlugins"))) {
    if (enabled && !/\s/.test(id)) console.log(id);
  }
}
' "$settings" "$1"
}

# "<id>\t<scope>" for the install records that apply here. Records in the shared
# volume are keyed by project path, so the listing spans every project mounted
# against it — another project's record is neither installed here nor ours.
records_here() {
    claude plugins list --json 2>/dev/null | node -e '
let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  let plugins = [];
  try { plugins = JSON.parse(input); } catch (e) {}
  if (!Array.isArray(plugins)) plugins = [];
  const here = process.argv[1];
  for (const p of plugins) {
    if (!p || !p.id) continue;
    // No projectPath means a user-scoped record, which applies everywhere.
    if (!p.projectPath || p.projectPath === here) {
      console.log(p.id + "\t" + (p.scope || "user"));
    }
  }
});
' "$project_dir"
}

# 1. Register declared marketplaces the volume does not know yet — a marketplace
#    that exists only as a settings.json declaration is invisible to `install`.
known_marketplaces="$(claude plugins marketplace list --json 2>/dev/null | node -e '
let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  let entries = [];
  try { entries = JSON.parse(input); } catch (e) {}
  if (!Array.isArray(entries)) entries = [];
  for (const m of entries) {
    if (m && m.name) console.log(m.name);
  }
});
')"

read_declared marketplaces | while IFS=$'\t' read -r name source; do
    [ -n "$name" ] && [ -n "$source" ] || continue
    printf '%s\n' "$known_marketplaces" | grep -qxF "$name" && continue
    # local, not the CLI's default of user: a user-scoped registration lands in
    # the shared volume, making one project's marketplace a resolvable plugin
    # source for every other project in the container.
    claude plugins marketplace add "$source" --scope local 2>/dev/null || true
done

# 2. Refresh metadata so the passes below resolve to the newest version the
#    declared ref allows.
claude plugins marketplace update 2>/dev/null || true

# 3. Install what this project declares but does not have. Updating alone left a
#    project whose plugins were never installed for its path with nothing — the
#    plugin reads as enabled but uncached, cleared by hand on every new project.
installed_here="$(records_here | cut -f1)"
read_declared plugins | while read -r plugin_id; do
    [ -n "$plugin_id" ] || continue
    printf '%s\n' "$installed_here" | grep -qxF "$plugin_id" && continue
    # local, not project: project scope writes enablement into the tracked
    # settings.json. No --yes: a plugin that installs by running a
    # marketplace-declared command needs that command accepted, which is not an
    # unattended hook's call to make. Those are left for a manual install.
    claude plugins install "$plugin_id" --scope local 2>/dev/null || true
done

# 4. `claude plugins update` has no bulk form, so update each within its own
#    scope. Scoping to this project is what fixes the old note that
#    project-scoped updates "are swallowed otherwise".
records_here | while IFS=$'\t' read -r plugin_id scope; do
    [ -n "$plugin_id" ] || continue
    claude plugins update "$plugin_id" --scope "$scope" 2>/dev/null || true
done
