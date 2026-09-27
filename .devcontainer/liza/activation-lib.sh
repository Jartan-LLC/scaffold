# shellcheck shell=bash
# Sourced by shim.sh and deactivate.sh, which both work on the activation record.

# Prints "<path> <fingerprint>" for each existing file or symlink given, so activation
# can record what it created and deactivation can tell whether it has changed since.
fingerprint() {
    local f
    for f in "$@"; do
        if [ -L "$f" ]; then
            echo "$f link:$(readlink "$f")"
        elif [ -f "$f" ]; then
            echo "$f $(sha256sum <"$f" | cut -d' ' -f1)"
        fi
    done
}

# Prints the absolute path of a path inside the git dir, for the clone at $1.
git_path() {  # top  git-path
    local p
    p=$(git -C "$1" rev-parse --git-path "$2") || return
    [[ "$p" == /* ]] && echo "$p" || echo "$1/$p"
}
