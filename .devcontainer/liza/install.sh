#!/bin/bash
# Installs the pinned Liza binary and ripgrep into ~/.liza (a per-project volume), puts
# the `liza` shim and `rg` on PATH, and refreshes Liza's global files to match the binary.

set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=.devcontainer/fetch-verified.sh
source "$here/../fetch-verified.sh"

# To move to a newer release: set LIZA_RELEASE and recompute the digest of that
# release's checksums.txt, which covers every platform's archive:
#   curl -fsSL https://github.com/liza-mas/liza/releases/download/<tag>/checksums.txt | sha256sum
LIZA_RELEASE="v0.9.1"
LIZA_CHECKSUMS_SHA256="6768ed207882b130d30257896ad898ccc01f3a2ab8e0c4df711f4a96bdaa839a"

# Liza's contracts and skills call `rg` by name; the container's `rg` is only a Claude
# Code shell function, invisible to the processes Liza spawns. Digests are upstream's
# per-asset .sha256 files, pinned here.
RG_VERSION="15.2.0"
declare -A RG_SHA256=(
    [x86_64]="33e15bcf1624b25cdd2a55813a47a2f95dbe126268203e76aa6a585d1e7b149c"
    [aarch64]="800b1e7206afe799dfb5a6901f23147cfaabe0e52210538100f61e86e1740915"
)

liza_home="$HOME/.liza"
real_liza="$liza_home/libexec/liza"
path_dir="$HOME/.local/bin"

case "$(uname -m)" in
    x86_64 | amd64) arch=x86_64 goarch=amd64 ;;
    aarch64 | arm64) arch=aarch64 goarch=arm64 ;;
    *) echo "Warning: Liza: unsupported architecture $(uname -m); skipped" >&2; exit 1 ;;
esac

mkdir -p "$liza_home" 2>/dev/null
# Fresh named volumes are root-owned.
[ -O "$liza_home" ] || sudo chown "$(id -u):$(id -g)" "$liza_home" \
    || echo "Warning: could not fix ownership on $liza_home" >&2
mkdir -p "$liza_home/libexec" "$liza_home/bin" "$path_dir"

install_liza() {
    local tmp archive base
    tmp=$(mktemp -d)
    archive="liza-${LIZA_RELEASE#v}-linux-${goarch}.tar.gz"
    base="https://github.com/liza-mas/liza/releases/download/${LIZA_RELEASE}"
    fetch_verified "$base/checksums.txt" "$LIZA_CHECKSUMS_SHA256" "$tmp/checksums.txt" \
        && curl -fsSL "$base/$archive" -o "$tmp/$archive" \
        && (cd "$tmp" && awk -v f="$archive" '$2 == f' checksums.txt | sha256sum --check --status) \
        && tar -xzf "$tmp/$archive" -C "$tmp" liza \
        && install -m 755 "$tmp/liza" "$real_liza"
    local rc=$?
    rm -rf "$tmp"
    return $rc
}

install_ripgrep() {
    local tmp name="ripgrep-${RG_VERSION}-${arch}-unknown-linux-musl"
    tmp=$(mktemp -d)
    fetch_verified "https://github.com/BurntSushi/ripgrep/releases/download/${RG_VERSION}/${name}.tar.gz" \
            "${RG_SHA256[$arch]}" "$tmp/rg.tar.gz" \
        && tar -xzf "$tmp/rg.tar.gz" -C "$tmp" "$name/rg" \
        && install -m 755 "$tmp/$name/rg" "$liza_home/bin/rg"
    local rc=$?
    rm -rf "$tmp"
    return $rc
}

if ! "$real_liza" version 2>/dev/null | grep -qx "liza version ${LIZA_RELEASE#v}"; then
    echo "Installing Liza ${LIZA_RELEASE}..."
    install_liza || { echo "Warning: Liza install failed (download or checksum mismatch)" >&2; exit 1; }
fi
if ! "$liza_home/bin/rg" --version 2>/dev/null | grep -q "^ripgrep ${RG_VERSION} "; then
    echo "Installing ripgrep ${RG_VERSION}..."
    install_ripgrep || echo "Warning: ripgrep install failed (download or checksum mismatch)" >&2
fi

ln -sfn "$here/shim.sh" "$path_dir/liza"
ln -sfn "$liza_home/bin/rg" "$path_dir/rg"

if [ "${INSTALL_LIZA_TOOLS:-false}" = true ]; then
    agent_tools="$here/AGENT_TOOLS.md"
else
    agent_tools="$here/AGENT_TOOLS.minimal.md"
fi

# --force every time keeps the contracts and skills matched to the pinned binary across
# version bumps, and reinstalls scaffold's AGENT_TOOLS.md over Liza's default.
"$real_liza" setup --force --yes --agent-tools "$agent_tools" </dev/null >/dev/null \
    || { echo "Warning: liza setup failed" >&2; exit 1; }

# setup links every skill into ~/.claude/skills, which loads them in every project that
# shares ~/.claude. The shim links them into the activated project instead.
for link in "$HOME"/.claude/skills/*; do
    [ -L "$link" ] || continue
    case "$(readlink "$link")" in
        "$liza_home"/skills/*) rm -- "$link" ;;
    esac
done
