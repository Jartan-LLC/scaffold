#!/bin/bash
# An unset variable is a typo, so it stops the script. No set -e or pipefail: each
# install step is best-effort and reports its own failure, and the rest still runs.
set -u

echo "Setting up development environment..."

source .devcontainer/fetch-verified.sh

# Installed here, not via the devcontainer feature: the feature installs as root,
# leaving @anthropic-ai unwritable so auto-update fails forever. Must precede
# codebase-memory-mcp, which registers its MCP server only if claude is present.
# Unpinned on purpose, unlike every other fetch here: it is kept self-updating.
echo "Installing Claude Code CLI..."
claude_install_failed=0
# Retry once: a registry blip during create otherwise costs a rebuild.
npm install -g @anthropic-ai/claude-code \
    || npm install -g @anthropic-ai/claude-code \
    || claude_install_failed=1

# Pinned from ci/requirements.txt so the container matches CI, and bootstrapped
# with pip because that is what the python devcontainer feature ships.
echo "Installing uv..."
uv_pin=$(sed -n 's/^\(uv==[^[:space:]]*\).*/\1/p' ci/requirements.txt 2>/dev/null | head -1)
if [ -n "$uv_pin" ]; then
    pip install "$uv_pin" || echo "Warning: uv install failed ($uv_pin)" >&2
else
    echo "Warning: no pinned uv in ci/requirements.txt; Python installs below will fail" >&2
fi

# Into the system Python: containerEnv sets UV_SYSTEM_PYTHON (Makefile, environment selection).
echo "Installing project dependencies (make install)..."
make_install_failed=false
make install || make_install_failed=true

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

    # The gh-config volume is root-owned when fresh, and so is ~/.config if the mount
    # had to create it. The parent stays non-recursive: it holds other tools' files.
    sudo chown vscode:vscode "$HOME/.config" || echo "Warning: could not fix ownership on $HOME/.config" >&2
    sudo chown -R vscode:vscode "$HOME/.config/gh" || echo "Warning: could not fix ownership on $HOME/.config/gh" >&2
fi

# Optional: Headroom token compression proxy (https://github.com/chopratejas/headroom)
# Reduces token usage 60-95% by compressing context sent to the LLM.
# Uncomment to enable:
# uv pip install --system "headroom-ai[proxy]"
# headroom init claude

# Install codebase-memory-mcp (structural code graph for Claude Code). This
# container can reach the host Docker socket, so the fetch is pinned three ways:
# install.sh by commit and digest, checksums.txt by digest (the installer checks
# every archive against it), and the release via CBM_DOWNLOAD_URL.
# Known gap: install.sh refetches checksums.txt after our check; verifying the
# release's sigstore bundles would close it and retire the manual digest bump.
# To bump: set CBM_RELEASE to the new tag and CBM_INSTALLER_COMMIT to that tag's
# commit, then recompute both digests with `curl -fsSL <url> | sha256sum`.
CBM_RELEASE="v0.10.5"
CBM_INSTALLER_COMMIT="77195634e13fd3bcd0d24543de5f876b4679f1cf"  # frozen: v0.10.5
CBM_INSTALLER_SHA256="2fdd4d6563fc8e540bb32e233c5fdef22ecf05d7ebd5a80657cd4fec953b3475"
CBM_CHECKSUMS_SHA256="6fbd04babc7815b5f2dc4b3330ff9a8f1728a1375aecd94ff13534fe2e02e764"
CBM_BASE_URL="https://github.com/DeusData/codebase-memory-mcp/releases/download/${CBM_RELEASE}"

# Skipped when INSTALL_LIZA_TOOLS is on: Liza's toolchain replaces it (liza/tools.sh).
if [ "${INSTALL_LIZA_TOOLS:-false}" != true ] && ! command -v codebase-memory-mcp &>/dev/null; then
    echo "Installing codebase-memory-mcp ${CBM_RELEASE}..."
    cbm_tmp=$(mktemp -d)
    if fetch_verified \
            "https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/${CBM_INSTALLER_COMMIT}/install.sh" \
            "$CBM_INSTALLER_SHA256" "$cbm_tmp/install.sh" \
        && fetch_verified \
            "${CBM_BASE_URL}/checksums.txt" \
            "$CBM_CHECKSUMS_SHA256" "$cbm_tmp/checksums.txt"; then
        # The installer exits non-zero when it can't register the MCP server through the
        # ~/.claude.json symlink made above; Claude Code's own command writes through it.
        CBM_DOWNLOAD_URL="$CBM_BASE_URL" bash "$cbm_tmp/install.sh"
        if [ ! -x "$HOME/.local/bin/codebase-memory-mcp" ] \
            || ! { claude mcp get codebase-memory-mcp >/dev/null 2>&1 \
                || claude mcp add --scope user codebase-memory-mcp -- "$HOME/.local/bin/codebase-memory-mcp" >/dev/null; }; then
            echo "Warning: codebase-memory-mcp install failed" >&2
        fi
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

# Liza always installs; ACTIVATE_LIZA and INSTALL_LIZA_TOOLS (containerEnv, on by
# default) activate it and add its toolchain. See .devcontainer/liza/README.md.
liza_installed=false liza_tools_failed=false liza_activation_failed=false
if bash .devcontainer/liza/install.sh; then
    liza_installed=true
    # Run here so a failure is recorded; activate.sh's own tools.sh run then skips
    # every tool whose pin already matches.
    if [ "${INSTALL_LIZA_TOOLS:-false}" = true ]; then
        bash .devcontainer/liza/tools.sh || liza_tools_failed=true
    fi
    if [ "${ACTIVATE_LIZA:-false}" = true ]; then
        bash .devcontainer/liza/activate.sh </dev/null >/dev/null || liza_activation_failed=true
    fi
fi

gh auth status 2>/dev/null || echo "Warning: gh not authenticated. Run 'gh auth login' to enable GitHub CLI." >&2
$liza_installed && [ ! -L CLAUDE.local.md ] && echo "Note: Liza is installed but not active here. Run 'bash .devcontainer/liza/activate.sh' to activate it for this clone, or see .devcontainer/liza/README.md." >&2

# Reported here, at the end, so it survives the dependency-install output above
# rather than scrolling away. Not fatal: a non-zero postCreateCommand makes the
# spec skip postStart and postAttach, losing the Docker socket fix and the
# Codespaces path override.
if [ "$claude_install_failed" = 1 ]; then
    echo "ERROR: Claude Code CLI install failed. Run 'npm install -g @anthropic-ai/claude-code' to retry." >&2
fi
if $make_install_failed; then
    echo "ERROR: Project dependency install failed (see make's output above). Run 'make install' to retry." >&2
fi
if $liza_installed && [ ! -x "$HOME/.liza/bin/rg" ]; then
    echo "ERROR: ripgrep install failed; Liza's agents search with rg. Run 'bash .devcontainer/liza/install.sh' to retry." >&2
fi
if $liza_tools_failed; then
    echo "ERROR: Liza toolchain install failed (see the warning above). Run 'bash .devcontainer/liza/tools.sh' to retry." >&2
fi
if $liza_activation_failed; then
    echo "ERROR: Liza activation failed. Run 'bash .devcontainer/liza/activate.sh' to retry." >&2
fi

echo "Development environment setup complete!"
