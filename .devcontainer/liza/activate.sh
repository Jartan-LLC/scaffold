#!/bin/bash
# Activates Liza for this clone. With INSTALL_LIZA_TOOLS=true it installs the toolchain
# first, which `liza init` must find in place. Extra arguments go to `liza init`.

here=$(cd "$(dirname "$0")" && pwd)

if [ "${INSTALL_LIZA_TOOLS:-false}" = true ]; then
    bash "$here/tools.sh" || echo "Warning: activating with the Liza tools that did install" >&2
fi
exec "$HOME/.local/bin/liza" init --claude --yes "$@"
