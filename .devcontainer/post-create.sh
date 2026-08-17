#!/bin/bash

echo "Setting up development environment..."

# Enable pnpm via corepack (ships with Node.js)
sudo corepack enable || echo "Warning: corepack enable failed; pnpm may not be available" >&2

# Installed here, not via the devcontainer feature: the feature installs as root,
# leaving @anthropic-ai unwritable so auto-update fails forever. Must precede
# codebase-memory-mcp, which registers its MCP server only if claude is present.
#
# Deliberately unpinned, and the one exception to the pinning rule this file
# otherwise follows: Claude Code is kept free to auto-update because its
# freshness is what makes it useful (Jonathan, JAR-220). Pinning it here would
# also fight the non-root install above, which exists to let it self-update.
echo "Installing Claude Code CLI..."
claude_install_failed=0
# Retry once: a registry blip during create otherwise costs a rebuild.
npm install -g @anthropic-ai/claude-code \
    || npm install -g @anthropic-ai/claude-code \
    || claude_install_failed=1

# Install Node.js dependencies from all package.json files
echo "Installing Node.js dependencies..."
while IFS= read -r -d '' pkg_file; do
    dir=$(dirname "$pkg_file")
    echo "  Installing from $dir..."
    (cd "$dir" && CI=true pnpm install) || echo "Warning: pnpm install failed in $dir" >&2
done < <(find . -name "package.json" -not -path "*/node_modules/*" -not -path "*/.pnpm-store/*" -type f -print0)

# uv installs every Python dependency below, in place of pip. Its version comes
# from ci/requirements.txt — the one line CI's setup-uv reads too — so the
# container, the local gate and the runner never drift apart, and Dependabot's
# "/ci" entry moves all three at once. Bootstrapped with pip because pip is what
# the python devcontainer feature ships; nothing else here uses it.
echo "Installing uv..."
uv_pin=$(sed -n 's/^\(uv==[^[:space:]]*\).*/\1/p' ci/requirements.txt 2>/dev/null | head -1)
if [ -n "$uv_pin" ]; then
    pip install "$uv_pin" || echo "Warning: uv install failed ($uv_pin)" >&2
else
    echo "Warning: no pinned uv in ci/requirements.txt; Python installs below will fail" >&2
fi

# --system: the container is the isolation, so packages go to its interpreter
# rather than a venv. uv refuses a non-venv target without this.
echo "Installing Python dependencies..."
while IFS= read -r -d '' req_file; do
    echo "  Installing from $req_file..."
    uv pip install --system -r "$req_file" || echo "Warning: uv pip install failed for $req_file" >&2
done < <(find . -name "requirements.txt" -not -path "*/.venv/*" -not -path "*/venv/*" -not -path "*/.tox/*" -type f -print0)

# Install Python dependencies from all pyproject.toml files (editable installs)
echo "Installing Python editable packages..."
while IFS= read -r -d '' pyproject_file; do
    dir=$(dirname "$pyproject_file")
    echo "  Installing from $dir..."
    uv pip install --system -e "${dir}[dev]" || echo "Warning: uv pip install failed for $dir" >&2
done < <(find . -name "pyproject.toml" -not -path "*/.venv/*" -not -path "*/venv/*" -not -path "*/.tox/*" -type f -print0)

# pre-commit binary comes from the .[dev] install above.
if command -v pre-commit &>/dev/null && [ -f .pre-commit-config.yaml ]; then
    echo "Wiring pre-commit git hook..."
    pre-commit install || echo "Warning: pre-commit install failed" >&2
fi

# vscode-user-specific setup (volume mounts, ownership fixes)
if [ "$(whoami)" = "vscode" ]; then
    if [ -d "$HOME/.claude" ]; then
        # Fix ownership on Claude volume mount (fresh volumes are root-owned)
        sudo chown -R vscode:vscode "$HOME/.claude" || echo "Warning: could not fix ownership on $HOME/.claude" >&2

        # Persist ~/.claude.json across rebuilds by symlinking into the volume
        if [ ! -f "$HOME/.claude/claude.json" ]; then
            if [ -f "$HOME/.claude.json" ]; then
                cp "$HOME/.claude.json" "$HOME/.claude/claude.json" || echo "Warning: could not copy .claude.json to volume" >&2
            else
                echo '{}' > "$HOME/.claude/claude.json" || echo "Warning: could not create claude.json stub" >&2
            fi
        fi
        if [ -f "$HOME/.claude/claude.json" ]; then
            ln -sf "$HOME/.claude/claude.json" "$HOME/.claude.json" || echo "Warning: could not create claude.json symlink; config will not persist across rebuilds" >&2
        else
            echo "Warning: claude.json not created; config will not persist across rebuilds" >&2
        fi
    else
        echo "Warning: $HOME/.claude not found; config will not persist across rebuilds" >&2
    fi
fi

# Optional: Headroom token compression proxy (https://github.com/chopratejas/headroom)
# Reduces token usage 60-95% by compressing context sent to the LLM.
# Uncomment to enable:
# uv pip install --system "headroom-ai[proxy]"
# headroom init claude

# Install codebase-memory-mcp (structural code graph for Claude Code).
#
# This is the one place in the template that runs third-party code fetched at
# create time, and the container it runs in bind-mounts the host Docker socket
# (docker-outside-of-docker, below) — so nothing here is best-effort about
# provenance. Registered as SEC-2026-0054, High. Three things get pinned:
#
#   1. the installer script — fetched at a commit rather than a branch, so the
#      URL is an immutable content address, and its bytes are checked against
#      CBM_INSTALLER_SHA256 before bash ever sees them;
#   2. checksums.txt — pinned here rather than trusted from the release. The
#      installer verifies each archive against this file but fetches it from the
#      same location as the archive, so on its own that check is circular:
#      whoever can replace a release asset can replace the checksum file beside
#      it. One digest covers every architecture, because every archive is
#      verified through this file;
#   3. the release the installer downloads — CBM_DOWNLOAD_URL replaces the
#      installer's own /releases/latest/download default. A tag names a mutable
#      location, so this bounds *which* release, not *which bytes*; item 2 is
#      what makes the bytes fixed.
#
# Residual, accepted by Security at Low: the installer refetches checksums.txt
# itself, so a swap landing between our check and its fetch is not caught. The
# attacker still has to replace a published release asset rather than push to a
# default branch. Closing it fully means serving the assets from loopback
# (install.sh accepts an http://127.0.0.1 CBM_DOWNLOAD_URL) — not taken, because
# that path is documented upstream as being for testing, and a template every
# fork inherits should not depend on someone else's test seam. The durable fix
# is sigstore verification of the release bundles, which also removes the manual
# digest bump below; tracked as JAR-326.
#
# To move to a newer release: set CBM_RELEASE, read install.sh's commit at that
# tag, and recompute both digests with
#   curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/<commit>/install.sh | sha256sum
#   curl -fsSL https://github.com/DeusData/codebase-memory-mcp/releases/download/<tag>/checksums.txt | sha256sum
CBM_RELEASE="v0.10.5"
CBM_INSTALLER_COMMIT="77195634e13fd3bcd0d24543de5f876b4679f1cf"  # frozen: v0.10.5
CBM_INSTALLER_SHA256="2fdd4d6563fc8e540bb32e233c5fdef22ecf05d7ebd5a80657cd4fec953b3475"
CBM_CHECKSUMS_SHA256="6fbd04babc7815b5f2dc4b3330ff9a8f1728a1375aecd94ff13534fe2e02e764"
CBM_BASE_URL="https://github.com/DeusData/codebase-memory-mcp/releases/download/${CBM_RELEASE}"

# Fetch into a destination only if the bytes match the expected digest.
cbm_fetch_verified() {  # url  expected-sha256  destination
    curl -fsSL "$1" -o "$3" && echo "$2  $3" | sha256sum --check --status
}

# The old invocation passed `--ui`. Upstream removed that flag in v0.10.0 when
# the UI became part of the single archive, and the installer's arg loop has no
# default case, so it has been silently ignored ever since. Nothing is lost by
# dropping it: checksums.txt gives the `-ui-` and plain archives identical
# digests, so they are the same bytes under two names.
if ! command -v codebase-memory-mcp &>/dev/null; then
    echo "Installing codebase-memory-mcp ${CBM_RELEASE}..."
    cbm_tmp=$(mktemp -d)
    if cbm_fetch_verified \
            "https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/${CBM_INSTALLER_COMMIT}/install.sh" \
            "$CBM_INSTALLER_SHA256" "$cbm_tmp/install.sh" \
        && cbm_fetch_verified \
            "${CBM_BASE_URL}/checksums.txt" \
            "$CBM_CHECKSUMS_SHA256" "$cbm_tmp/checksums.txt"; then
        CBM_DOWNLOAD_URL="$CBM_BASE_URL" bash "$cbm_tmp/install.sh" \
            || echo "Warning: codebase-memory-mcp install failed" >&2
    else
        echo "Warning: codebase-memory-mcp installer or checksums.txt did not match its pinned digest; install skipped" >&2
    fi
    rm -rf "$cbm_tmp"
fi

# Enable codebase-memory-mcp auto-indexing (indexes each project on first MCP
# session and re-indexes in the background on git changes). Guarded because the
# install above is best-effort; idempotent, so it re-applies on every rebuild.
if command -v codebase-memory-mcp &>/dev/null; then
    codebase-memory-mcp config set auto_index true || echo "Warning: could not enable codebase-memory-mcp auto_index" >&2
fi

gh auth status 2>/dev/null || echo "Warning: gh not authenticated. Run 'gh auth login' to enable GitHub CLI." >&2

# Reported here, at the end, so it survives the dependency-install output above
# rather than scrolling away. Not fatal: a non-zero postCreateCommand makes the
# spec skip postStart and postAttach, losing the Docker socket fix and the
# Codespaces path override.
if [ "$claude_install_failed" = 1 ]; then
    echo "ERROR: Claude Code CLI install failed. Run 'npm install -g @anthropic-ai/claude-code' to retry." >&2
fi

echo "Development environment setup complete!"
