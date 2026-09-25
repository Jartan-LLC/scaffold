#!/bin/bash
# INSTALL_LIZA_TOOLS: installs Liza's agent toolchain into ~/.liza (a per-project volume),
# pinned in place of `liza toolchain install`, which fetches unpinned installers from
# upstream default branches. Each tool records its pin in ~/.liza/bin/.pins/ so a re-run
# installs only what changed. Needs install.sh to have run first.

set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=.devcontainer/fetch-verified.sh
source "$here/../fetch-verified.sh"

liza_home="$HOME/.liza"
bin="$liza_home/bin"
lib="$liza_home/lib"
pins="$bin/.pins"

# Release binaries. Digests are computed from the downloaded assets and match the
# digests GitHub reports for them (`gh release view -R <repo> --json assets`).
AST_GREP_VERSION="0.45.3"
declare -A AST_GREP_SHA256=(
    [x86_64]="f8ac830881339d1edee6b2652f54798c0f4da5a827f2db38a08ee31117783ce8"
    [aarch64]="b39cfbc58da4b869a88b8a4bc57bd5deb0d24541e704cf7c257da7b53ec81c8f"
)
YQ_VERSION="v4.53.6"
declare -A YQ_SHA256=(
    [x86_64]="c5f056448f973ae7d39b5401949648a78f2dc1947d6a8eb65be60d5c504b9385"
    [aarch64]="88a1016bc1d657375a35864e4f44b6f333df8ff97b559f51bba0adcb2169df09"
)
# x86_64 only: rtk's one arm64 Linux build needs glibc 2.39, newer than Debian 12's
# (scaffold issue 124), and mdq publishes no arm64 Linux build.
RTK_VERSION="v0.50.0"
RTK_SHA256_X86_64="bc2b8902b0d9c796c82ef45f16ae2307e17757afeca5ee156235a3dc7bda5f89"
MDQ_VERSION="v0.10.0"
MDQ_SHA256_X86_64="673ed676382f54a21e4381d845236c776b2b71ed8dc1cc3e92cf6d66a39edb07"

# Built from source: none of these publish release binaries. A commit SHA fixes the
# source, and each go.sum fixes the dependencies. Each builds from ./cmd/<name>.
declare -A GO_TOOLS=(
    [stacklit]="liza-mas/stacklit-cli c8a87a75116e675f67e5ca71197b6deee55142b2"
    [scip-search]="liza-mas/scip-search b8c1487bb4cbdb6483a61c376b81eb3d77d8cc1f"  # v0.2.1
    [functional-clusters]="liza-mas/functional-clusters f1ac506508752660214d4a6d35fd33113177a482"
    [mdtoc]="liza-mas/mdtoc 37712275e36b5aef9c9651e633b1896e22d917f3"
    [bash-policy]="liza-mas/bash-policy 7260ac81da9bbaad89e1737e68239f0f04a7558e"
)

# semble's embedding model, fetched at a fixed Hugging Face revision so it never
# downloads at runtime (SEMBLE_MODEL_NAME points semble at the local copy).
SEMBLE_MODEL="minishlab/potion-code-16M-v2"
SEMBLE_MODEL_REVISION="e9d2a44ca6a05ac6685f3b23709ea57eb7352d5b"
declare -A SEMBLE_MODEL_SHA256=(
    [config.json]="148e5691a6fcc553437156859701fba017a1ba5d340b170f17e0f3668fb861a7"
    [model.safetensors]="75cf7a6c2171b230ad19b1e7d8e0b1aee86da5a02af8e7cacedd9921d227623c"
    [modules.json]="a68dcbed0429dcdd5bfdca92b0b03cc30d09122c0a3fcf4758787d4b244e45b2"
    [tokenizer.json]="107bbdcbad4bff1d299b7a4c3a2fb17c52890688b7dd0e4c9deab79d3c4f3d45"
)

case "$(uname -m)" in
    x86_64 | amd64) arch=x86_64 goarch=amd64 ;;
    aarch64 | arm64) arch=aarch64 goarch=arm64 ;;
    *) echo "Warning: Liza tools: unsupported architecture $(uname -m); skipped" >&2; exit 1 ;;
esac

mkdir -p "$bin" "$lib" "$pins"
failed=()

# Runs an installer unless the tool's recorded pin already matches.
install_pinned() {  # tool  pin  installer-command...
    local tool=$1 pin=$2
    [ "$(cat "$pins/$tool" 2>/dev/null)" = "$pin" ] && return 0
    echo "Installing $tool ($pin)..."
    if "${@:3}"; then
        echo "$pin" >"$pins/$tool"
    else
        failed+=("$tool")
    fi
}

# Downloads a release asset, checks its digest, and installs one binary from it.
release_binary() {  # tool  url  sha256  member-in-archive (empty for a bare binary)
    local tmp rc
    tmp=$(mktemp -d)
    fetch_verified "$2" "$3" "$tmp/asset" && case "$2" in
        *.zip) unzip -p "$tmp/asset" "$4" >"$tmp/$1" ;;
        *.tar.gz) tar -xzf "$tmp/asset" -O "$4" >"$tmp/$1" ;;
        *) mv "$tmp/asset" "$tmp/$1" ;;
    esac && install -m 755 "$tmp/$1" "$bin/$1"
    rc=$?
    rm -rf "$tmp"
    return $rc
}

go_build() {  # tool  repo  commit
    local src rc
    src=$(mktemp -d)
    git -C "$src" init -q \
        && git -C "$src" fetch -q --depth 1 "https://github.com/$2" "$3" \
        && git -C "$src" checkout -q FETCH_HEAD \
        && (cd "$src" && CGO_ENABLED=0 GOTOOLCHAIN=local GOFLAGS=-mod=readonly \
            go build -trimpath -o "$bin/$1" "./cmd/$1")
    rc=$?
    rm -rf "$src"
    return $rc
}

npm_tools() {
    local tool
    mkdir -p "$lib/npm" \
        && cp "$here/npm/package.json" "$here/npm/package-lock.json" "$lib/npm/" \
        && (cd "$lib/npm" && npm ci --ignore-scripts --no-audit --no-fund --no-update-notifier --loglevel=error) \
        && for tool in scip-python scip-typescript context7-mcp; do
            ln -sfn "$lib/npm/node_modules/.bin/$tool" "$bin/$tool" || return 1
        done
}

semble_tool() {
    local file
    uv venv -q --clear --python 3.12 "$lib/semble" \
        && uv pip install -q --python "$lib/semble/bin/python" --require-hashes \
            -r "$here/semble-requirements.txt" \
        && ln -sfn "$lib/semble/bin/semble" "$bin/semble" \
        && mkdir -p "$lib/semble-model" || return 1
    for file in "${!SEMBLE_MODEL_SHA256[@]}"; do
        fetch_verified "https://huggingface.co/$SEMBLE_MODEL/resolve/$SEMBLE_MODEL_REVISION/$file" \
            "${SEMBLE_MODEL_SHA256[$file]}" "$lib/semble-model/$file" || return 1
    done
}

install_pinned ast-grep "$AST_GREP_VERSION" release_binary ast-grep \
    "https://github.com/ast-grep/ast-grep/releases/download/$AST_GREP_VERSION/app-$arch-unknown-linux-gnu.zip" \
    "${AST_GREP_SHA256[$arch]}" ast-grep
install_pinned yq "$YQ_VERSION" release_binary yq \
    "https://github.com/mikefarah/yq/releases/download/$YQ_VERSION/yq_linux_$goarch" \
    "${YQ_SHA256[$arch]}" ""
if [ "$arch" = x86_64 ]; then
    install_pinned rtk "$RTK_VERSION" release_binary rtk \
        "https://github.com/rtk-ai/rtk/releases/download/$RTK_VERSION/rtk-x86_64-unknown-linux-musl.tar.gz" \
        "$RTK_SHA256_X86_64" rtk
    install_pinned mdq "$MDQ_VERSION" release_binary mdq \
        "https://github.com/yshavit/mdq/releases/download/$MDQ_VERSION/mdq-linux-x64-musl.tar.gz" \
        "$MDQ_SHA256_X86_64" mdq
else
    echo "Warning: rtk and mdq have no build that runs on arm64 Debian 12; skipped" >&2
fi
for tool in "${!GO_TOOLS[@]}"; do
    read -r repo commit <<<"${GO_TOOLS[$tool]}"
    install_pinned "$tool" "$commit" go_build "$tool" "$repo" "$commit"
done
install_pinned npm-tools "$(sha256sum <"$here/npm/package-lock.json")" npm_tools
install_pinned semble "$(sha256sum <"$here/semble-requirements.txt") $SEMBLE_MODEL_REVISION" semble_tool

# Writes ~/.liza/toolchain/env.sh (PATH plus the LIZA_ENABLE_* gates Liza reads) and
# sources it from the shell profiles. scip-go is excluded: it needs a Go project.
"$liza_home/libexec/liza" toolchain configure --profile full --exclude scip-go \
    --install-dir "$bin" --agent-tools skip --write-shell-profile </dev/null >/dev/null \
    || failed+=("toolchain configure")
echo "export SEMBLE_MODEL_NAME='$lib/semble-model'" >>"$liza_home/toolchain/env.sh"

if command -v claude >/dev/null; then
    # Local scope: registered for this project path only.
    claude mcp get context7 >/dev/null 2>&1 \
        || claude mcp add --scope local context7 -- "$bin/context7-mcp" >/dev/null \
        || failed+=("context7 MCP registration")
    # The toolchain replaces codebase-memory-mcp, whose registration is user-scope in the
    # shared ~/.claude volume: switch it off for this project only, as /mcp would.
    # ~/.claude.json is a symlink into the claude-data volume: edit its target, atomically.
    claude_json=$(readlink -f "$HOME/.claude.json")
    jq --arg p "$PWD" '.projects[$p].disabledMcpServers |= ((. // []) + ["codebase-memory-mcp"] | unique)' \
        "$claude_json" >"$claude_json.tmp" \
        && mv "$claude_json.tmp" "$claude_json" \
        || failed+=("codebase-memory-mcp disable")
fi

if [ ${#failed[@]} -gt 0 ]; then
    echo "Warning: Liza tools failed: ${failed[*]}" >&2
    exit 1
fi
