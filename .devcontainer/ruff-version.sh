#!/bin/bash
# Prints the ruff version in the ruff hook's "# frozen: vX.Y.Z" comment in
# .pre-commit-config.yaml, which post-create.sh installs and verify.sh checks.
# Exits 1 when the ruff hook has no such comment, 2 when there is no ruff hook.

set -u
# A repo: line, so a comment naming the hook doesn't count as the hook.
repo='^[[:space:]-]*repo:[[:space:]]*https://github\.com/astral-sh/ruff-pre-commit'
config=.pre-commit-config.yaml
grep -qE "$repo" "$config" 2>/dev/null || exit 2
# The patterns stop at the next repo: key and skip '- rev:' lines, so a ruff entry with
# rev: above repo: finds no version instead of taking the next hook's.
rev=$(sed -n "\|$repo|,/^[[:space:]-]*repo:/{/^[[:space:]]*rev:/{p;q}}" "$config")
version=$(sed -n 's/.*# frozen: v\([^[:space:]]*\).*/\1/p' <<<"$rev")
[ -n "$version" ] || exit 1
echo "$version"
