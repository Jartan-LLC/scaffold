# shellcheck shell=bash
# Sourced by shim.sh and deactivate.sh, which both work on the activation record.

# Prints "<path> <fingerprint>" for each existing file or symlink given, so activation
# can record what it created and deactivation can tell whether it has changed since.
# Readers split on the last space, so a symlink's target is hashed too.
fingerprint() {
    local f
    for f in "$@"; do
        if [ -L "$f" ]; then
            echo "$f link:$(readlink "$f" | sha256sum | cut -d' ' -f1)"
        elif [ -f "$f" ]; then
            echo "$f $(sha256sum <"$f" | cut -d' ' -f1)"
        fi
    done
}

# Puts a copy of file or symlink $1 at $2, replacing what's there without following it.
# A failed copy leaves $2 as it was.
put_copy() {  # source dest
    rm -f -- "$2.liza-tmp"
    cp -P -p -- "$1" "$2.liza-tmp" && mv -f -T -- "$2.liza-tmp" "$2" && return
    rm -f -- "$2.liza-tmp"
    return 1
}

# Prints the absolute path of a path inside the git dir, for the clone at $1.
git_path() {  # top  git-path
    local p
    p=$(git -C "$1" rev-parse --git-path "$2") || return
    [[ "$p" == /* ]] && echo "$p" || echo "$1/$p"
}
