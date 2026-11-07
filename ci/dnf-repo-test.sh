#!/usr/bin/env bash
# Tests the signed dnf repository packaging/dnf-repo.sh builds, from first install to
# upgrade, against the attacks repo_gpgcheck, gpgcheck and the key the package installs
# stop. ci.yml's dnf-repo job runs each mode as root in its own Fedora container, so the
# client starts with no keys.
#
# Usage:
#   ci/dnf-repo-test.sh build WWW
#     Builds 0.0.1, 0.0.2 and 0.0.3 with packaging/rpm.sh, from HEAD with a throwaway key
#     in packaging/RPM-GPG-KEY and packaging/dnf.repo's baseurl at the url below, signs the
#     first two with that key, and writes under WWW what ci/dnf_repo_server.py serves: the
#     Release assets under assets/, and one repository per scenario.
#     Needs what dnf-repo.sh and rpm.sh need, and zstd.
#   ci/dnf-repo-test.sh check WWW
#     Runs dnf against WWW, which ci/dnf_repo_server.py serves at the url below from
#     outside this container: python3 here would hold tzdata, which the Obsoletes check
#     needs dnf to be able to remove. Needs dnf5 5.4.7 or later and dnf5-plugin-automatic.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
readonly root
# ci.yml's dnf-repo job starts ci/dnf_repo_server.py on this port.
readonly url=http://127.0.0.1:8000
# build's scratch directory, which its EXIT trap removes.
work=''
# The file that holds the output of run's last command, which check reads.
log=''

die() {
    printf 'dnf-repo-test.sh: %s\n' "$*" >&2
    exit 1
}

# Prints the fingerprint of a new RSA-4096 signing key with no passphrase and no expiry.
new_key() {
    gpg --batch --quiet --passphrase '' --quick-gen-key "$1" rsa4096 sign never
    gpg --with-colons --fingerprint "$1" | awk -F: '/^fpr/ { print $10; exit }' # codespell:ignore fpr
}

build() {
    local www=$1 fingerprint other v rpm name
    work=$(mktemp -d)
    trap 'rm -rf -- "$work"' EXIT
    GNUPGHOME=$work/gnupg
    export GNUPGHOME
    mkdir -m 700 "$GNUPGHOME"
    fingerprint=$(new_key 'dnf-repo CI <ci@example.invalid>')
    gpg --armor --export "$fingerprint" >"$work/RPM-GPG-KEY"
    mkdir -p "$www/assets"

    # rpm.sh builds the commit checked out, so the packages come from a commit on top of
    # HEAD, in a clone, that holds the throwaway key and baseurl. The checkout stays as it
    # is. It belongs to the runner's user, not this container's root, and git checks the
    # owner of its .git directory.
    local src=$work/src
    git -c safe.directory="$root/.git" -c advice.detachedHead=false clone --quiet -- "$root" "$src"
    cp "$work/RPM-GPG-KEY" "$src/packaging/RPM-GPG-KEY"
    sed -i "s|^baseurl=.*|baseurl=$url/repo/|" "$src/packaging/dnf.repo"
    grep -qx "baseurl=$url/repo/" "$src/packaging/dnf.repo" ||
        die "packaging/dnf.repo has no baseurl line"
    git -C "$src" -c user.name=CI -c user.email=ci@example.invalid \
        commit --quiet --all --message 'The dnf-repo CI key and server'

    for v in 0.0.1 0.0.2 0.0.3; do
        rpm=$("$src/packaging/rpm.sh" "$v" "$work/rpms/v$v")
        name=$(basename "$rpm" .noarch.rpm)
        # 0.0.3 stays unsigned, as a release made before signing would be.
        [[ $v == 0.0.3 ]] ||
            "$root/packaging/dnf-repo.sh" sign "$fingerprint" "$work/RPM-GPG-KEY" "$rpm"
        cp -R "$work/rpms/v$v" "$www/assets/"
    done

    mkdir -p "$work/in1/v0.0.1"
    cp "$work/rpms/v0.0.1/$name.noarch.rpm" "$work/in1/v0.0.1/"
    bundle "$fingerprint" "$work/in1" "$work/out1" "$www/v1"
    # The unsigned 0.0.3 is left out: if it weren't, the client would fail to upgrade.
    bundle "$fingerprint" "$work/rpms" "$work/out2" "$www/v2" "$work/out1/$name-dnf-repo.tar.gz"
    local file
    while IFS= read -r file; do
        [[ -e $www/v2/repodata/$file ]] || die "v2 lacks $file, which v1's repomd.xml names"
    done < <(sed -n 's|.*<location href="repodata/\([^"/]*\)".*|\1|p' \
        "$www/v1/repodata/repomd.xml")

    # sign refuses a key the key file doesn't hold. A package signed by another key fails
    # metadata, and prune deletes it.
    other=$(new_key 'dnf-repo CI, another key <other@example.invalid>')
    gpg --armor --export "$other" >"$work/other-key"
    mkdir -p "$work/in-other/v0.0.3"
    cp "$work/rpms/v0.0.3/$name.noarch.rpm" "$work/in-other/v0.0.3/"
    refused "doesn't hold the key $other" \
        sign "$other" "$work/RPM-GPG-KEY" "$work/in-other/v0.0.3/$name.noarch.rpm"
    "$root/packaging/dnf-repo.sh" sign "$other" "$work/other-key" \
        "$work/in-other/v0.0.3/$name.noarch.rpm"
    refused 'a key not in the key file' metadata "$fingerprint" "$work/RPM-GPG-KEY" \
        "$url/releases/download/" "$work/in-other" "$work/out-other"
    # On a copy: the otherkey scenario below serves the package.
    cp -R "$work/in-other" "$work/pruned"
    "$root/packaging/dnf-repo.sh" prune "$work/RPM-GPG-KEY" "$work/pruned"
    [[ ! -e $work/pruned/v0.0.3/$name.noarch.rpm ]] ||
        die "dnf-repo.sh prune kept a package signed by another key"

    # Signed metadata that lists an unsigned package, which gpgcheck refuses.
    mkdir "$www/unsigned"
    createrepo_c --quiet --location-prefix "$url/releases/download/" \
        --outputdir "$www/unsigned" "$work/rpms"
    gpg --batch --armor --detach-sign --local-user "$fingerprint" "$www/unsigned/repodata/repomd.xml"

    # repomd.xml changed after it was signed.
    cp -R "$www/v2" "$www/tampered"
    sed -i 's|<revision>|<revision>1|' "$www/tampered/repodata/repomd.xml"

    # Someone who can change the site but has no key: every package obsoletes tzdata, and
    # repomd.xml names the new primary.xml with its checksums, under the old signature.
    cp -R "$www/v2" "$www/obsoletes"
    local primary
    primary=$(grep -o 'repodata/[^"]*-primary\.xml[^"]*' "$www/obsoletes/repodata/repomd.xml")
    zstd -dcq "$www/obsoletes/$primary" |
        sed 's|</rpm:provides>|&<rpm:obsoletes><rpm:entry name="tzdata"/></rpm:obsoletes>|' \
            >"$work/primary.xml"
    grep -q 'name="tzdata"' "$work/primary.xml" || die "no Obsoletes injected"
    modifyrepo_c --mdtype=primary "$work/primary.xml" "$www/obsoletes/repodata" >/dev/null

    # Someone who controls the site and holds another key: the metadata and the package are
    # validly signed by it, and the site serves it as the repository's key.
    mkdir "$www/otherkey"
    cp -R "$work/in-other/v0.0.3" "$www/otherkey/"
    createrepo_c --quiet "$www/otherkey"
    gpg --batch --armor --detach-sign --local-user "$other" "$www/otherkey/repodata/repomd.xml"
    gpg --armor --export "$other" >"$www/otherkey/RPM-GPG-KEY-$name"

    # A signing subkey isn't a key the package installs, though the key file holds it. After
    # every signature by $other, as gpg would sign with the subkey from now on.
    gpg --batch --quiet --passphrase '' --quick-add-key "$other" ed25519 sign never
    local subkey
    subkey=$(gpg --with-colons --with-subkey-fingerprint --list-keys "$other" |
        awk -F: '$1 == "sub" { s = 1; next } s && $1 == "fpr" { print $10; exit }') # codespell:ignore fpr
    [[ -n $subkey ]] || die "gpg added no subkey"
    gpg --armor --export "$other" >"$work/other-key"
    refused "doesn't hold the key $subkey" \
        sign "$subkey" "$work/other-key" "$work/rpms/v0.0.3/$name.noarch.rpm"
}

# Runs dnf-repo.sh with the arguments after $1, which must fail with the message $1.
refused() {
    local message=$1
    shift
    if "$root/packaging/dnf-repo.sh" "$@" 2>"$work/refused.err"; then
        die "dnf-repo.sh $1 succeeded where it should fail with: $message"
    fi
    grep -qF -- "$message" "$work/refused.err" || die "$(cat "$work/refused.err")"
}

# Builds the bundle of the RPMs in RPMDIR, signed by FINGERPRINT, into OUTDIR as a release
# would, with PREVIOUS as the bundle it replaces, and unpacks it into DEST.
bundle() {
    local fingerprint=$1 rpmdir=$2 outdir=$3 dest=$4 previous=${5:-} out
    out=$("$root/packaging/dnf-repo.sh" metadata "$fingerprint" "$work/RPM-GPG-KEY" \
        "$url/releases/download/" "$rpmdir" "$outdir" ${previous:+"$previous"})
    mkdir -p "$dest"
    tar -xzf "$out" -C "$dest"
}

check() {
    local www=$1 name
    log=$(mktemp)
    name=$(basename "$www"/v1/RPM-GPG-KEY-*)
    name=${name#RPM-GPG-KEY-}
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
        curl -fs -o /dev/null "$url/v1/repodata/repomd.xml" && break
        ((i < 10)) || die "nothing answers at $url, where ci/dnf_repo_server.py should serve"
        sleep 1
    done
    rpm -q tzdata >/dev/null || die "tzdata is not installed, so the Obsoletes check can't run"

    # The package installs the .repo file and key that every dnf command below uses.
    run dnf -y install "$url/releases/download/v0.0.1/$name.noarch.rpm"
    expect "$name" 0.0.1

    # With no terminal to confirm the key on: as a timer runs it.
    serve "$www" v2
    run dnf --repo="$name" automatic --installupdates </dev/null
    expect "$name" 0.0.2

    run dnf -y downgrade "$name"
    expect "$name" 0.0.1
    run dnf -y --refresh upgrade "$name"
    expect "$name" 0.0.2

    # Fedora sets skip_if_unavailable, so dnf exits 0 when it skips the repository: each
    # check below reads what is installed, not dnf's exit status.
    serve "$www" unsigned
    run dnf -y --refresh upgrade "$name" || true
    expect "$name" 0.0.2
    grep -q 'The package is not signed.' "$log" || die "dnf did not refuse the unsigned package"

    run dnf -y downgrade "$name"
    expect "$name" 0.0.1
    serve "$www" tampered
    run dnf -y --refresh upgrade "$name" || true
    expect "$name" 0.0.1
    grep -q 'repomd.xml GPG signature verification error: Bad PGP signature' "$log" ||
        die "dnf did not skip the tampered repository"

    serve "$www" obsoletes
    run dnf -y --refresh upgrade "$name" || true
    rpm -q tzdata >/dev/null || die "the injected Obsoletes removed tzdata"
    expect "$name" 0.0.1
    grep -q 'repomd.xml GPG signature verification error: Bad PGP signature' "$log" ||
        die "dnf did not skip the repository with the injected Obsoletes"

    serve "$www" otherkey
    run dnf -y --refresh upgrade "$name" || true
    expect "$name" 0.0.1
    grep -q 'repomd.xml GPG signature verification error: Signing key not found' "$log" ||
        die "dnf did not skip the repository signed by another key"
}

# Serves the scenario $2 under WWW $1 as the repository.
serve() {
    [[ -d $1/$2 ]] || die "no scenario $2"
    ln -sfn "$2" "$1/repo"
    printf '== the repository is now %s\n' "$2"
}

# Runs a command, showing its output and keeping it in the file $log for the checks to read.
run() {
    printf '$ %s\n' "$*"
    "$@" 2>&1 | tee "$log"
}

expect() {
    local got
    got=$(rpm -q --qf '%{VERSION}' "$1") || got='not installed'
    [[ $got == "$2" ]] || die "expected $1 $2 installed, found $got"
    printf '== %s %s is installed\n' "$1" "$2"
}

(($# == 2)) || die "usage: ci/dnf-repo-test.sh build|check WWW"
case $1 in
    build) build "$2" ;;
    check) check "$2" ;;
    *) die "usage: ci/dnf-repo-test.sh build|check WWW" ;;
esac
