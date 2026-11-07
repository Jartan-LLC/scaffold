#!/usr/bin/env bash
# Signs RPMs, and builds the signed dnf repository metadata for RPMs a GitHub Release holds.
# Needs rpm, rpmsign, rpmkeys, createrepo_c, gpg and tar, as the Fedora container in ci.yml's
# dnf-repo job has. gpg signs with the secret key FINGERPRINT from its keyring
# ($GNUPGHOME), which must have no passphrase.
#
# Usage:
#   packaging/dnf-repo.sh sign FINGERPRINT KEYFILE RPM
#     Signs RPM in place with the key FINGERPRINT, which must be a primary key in KEYFILE.
#   packaging/dnf-repo.sh metadata FINGERPRINT KEYFILE URL RPMDIR OUTDIR [PREVIOUS]
#     Indexes RPMDIR/vX.Y.Z/NAME.noarch.rpm for each release, with each package's
#     location URL as URL, which ends in /, then vX.Y.Z/NAME.noarch.rpm. Leaves out an
#     unsigned RPM, with a warning. Writes OUTDIR/NAME-dnf-repo.tar.gz, holding repodata/
#     with repomd.xml signed by FINGERPRINT, and KEYFILE as RPM-GPG-KEY-NAME, and prints
#     its path. PREVIOUS is the bundle this replaces, if any. FINGERPRINT must be a primary
#     key in KEYFILE.
#   packaging/dnf-repo.sh prune KEYFILE RPMDIR
#     Deletes each RPMDIR/vX.Y.Z/NAME.noarch.rpm signed by a key not in KEYFILE, with a
#     warning, so metadata, which fails on one, can index the rest: an earlier release's RPM
#     is one once a key rotation or leak takes its key out of KEYFILE. Fails on a damaged
#     RPM or a bad signature, as metadata does.
#   packaging/dnf-repo.sh fingerprint
#     Prints the fingerprint of the one secret key in gpg's keyring, and fails unless the
#     keyring holds exactly one.
set -euo pipefail

die() {
    printf 'dnf-repo.sh: %s\n' "$*" >&2
    exit 1
}

usage() {
    die "usage: packaging/dnf-repo.sh sign FINGERPRINT KEYFILE RPM
       packaging/dnf-repo.sh metadata FINGERPRINT KEYFILE URL RPMDIR OUTDIR [PREVIOUS]
       packaging/dnf-repo.sh prune KEYFILE RPMDIR
       packaging/dnf-repo.sh fingerprint"
}

# A full fingerprint, so gpg can't pick another key whose ID or user ID matches.
check_fingerprint() {
    [[ $1 =~ ^[0-9A-Fa-f]{40}$ ]] || die "not a key fingerprint (40 hex digits): $1"
}

# Prints each primary key's fingerprint in gpg's --with-colons listing on stdin. gpg lists
# it, in uppercase, in the first fingerprint record after the key's pub or sec record. The
# others are its subkeys', and the rvk records before it name designated revokers, keys the
# listing needn't hold.
primary_fingerprints() {
    awk -F: '
        $1 == "pub" || $1 == "sec" { p = 1; next }
        p && $1 == "fpr" { print $10; p = 0 }' # codespell:ignore fpr
}

# Users trust only the keys the package installs from key file $2: dnf skips a repository
# whose repomd.xml another key signed, with only a warning.
check_key() {
    [[ -f $2 ]] || die "no such key file: $2"
    local keys key
    keys=$(gpg --batch --with-colons --show-keys -- "$2" 2>&1) ||
        die "can't read the keys in $2: $keys"
    key=$(printf '%s' "$1" | tr a-f A-F)
    # Not grep -q, which can stop reading before awk finishes and fail the pipeline.
    primary_fingerprints <<<"$keys" | grep -xF -- "$key" >/dev/null ||
        die "$2 doesn't hold the key $1"
}

sign() {
    (($# == 3)) || usage
    check_fingerprint "$1"
    check_key "$1" "$2"
    [[ -f $3 ]] || die "no such RPM: $3"
    # rpm 6 reads _openpgp_sign_id, rpm 4 _gpg_name.
    rpmsign --addsign --define "_openpgp_sign_id $1" --define "_gpg_name $1" -- "$3" >&2
}

# Imports the keys in key file $2 into a new keyring database $1.
import_keys() {
    mkdir "$1"
    rpmkeys --dbpath "$1" --import "$2" || die "can't read the keys in $2"
}

# Prints "signed" when RPM $1 has signatures and each verifies with a key in the keyring
# database $2, "unsigned" when it has none, "other key" when it is intact and each signature
# that fails is by a key not in $2, and fails otherwise.
signature() {
    local out checks status=0
    out=$(rpmkeys --dbpath "$2" -Kv -- "$1" 2>&1) || status=$?
    # The first line is the RPM's path, which could hold any of the text matched below.
    checks=${out#*$'\n'}
    # rpmkeys names the key of each signature it finds ("Signature, key" in rpm 4). With
    # none, rpm 6 fails the check and rpm 4 passes it, so the status alone can't tell.
    if [[ $checks == *[Ss]"ignature, key "* ]]; then
        if ((status == 0)); then
            echo signed
            return
        fi
        # rpmkeys marks a signature whose key it lacks NOKEY, and a check that fails BAD.
        if [[ $checks == *": NOKEY"* && $checks != *": BAD"* ]] &&
            rpmkeys --dbpath "$2" -K --nosignature -- "$1" >/dev/null 2>&1; then
            echo other key
            return
        fi
        die "$1 has a bad signature, or is damaged:
$out"
    fi
    rpmkeys --dbpath "$2" -K --nosignature -- "$1" >/dev/null 2>&1 ||
        die "$1 is damaged:
$out"
    echo unsigned
}

# A subshell, so the EXIT trap removes the scratch directory when metadata returns.
metadata() (
    (($# == 5 || $# == 6)) || usage
    local fingerprint=$1 keyfile=$2 url=$3 rpmdir=$4 outdir=$5 previous=${6:-}
    check_fingerprint "$fingerprint"
    check_key "$fingerprint" "$keyfile"
    [[ $url == */ ]] || die "the URL must end in /: $url"
    [[ -z $previous || -f $previous ]] || die "no such bundle: $previous"

    local work
    work=$(mktemp -d)
    trap 'rm -rf -- "$work"' EXIT
    mkdir "$work/packages" "$work/bundle"
    import_keys "$work/keyring" "$keyfile"

    local rpm tag nv pkg version sig name='' count=0
    shopt -s nullglob
    for rpm in "$rpmdir"/*/*.rpm; do
        tag=$(basename -- "$(dirname -- "$rpm")")
        nv=$(rpm -qp --nosignature --qf '%{NAME} %{VERSION}' -- "$rpm") ||
            die "not an RPM: $rpm"
        pkg=${nv%% *}
        version=${nv#* }
        # A ~ is how rpm.sh writes a pre-release, and dnf would upgrade every user to one:
        # it sorts 2.0.0~rc.1 above 1.1.0.
        [[ $version != *"~"* ]] || die "$rpm is a pre-release ($version)"
        [[ $tag == "v$version" ]] || die "$rpm is version $version, not ${tag#v}"
        sig=$(signature "$rpm" "$work/keyring")
        case $sig in
            signed) ;;
            unsigned)
                # Releases made before the project signed its RPMs.
                printf 'dnf-repo.sh: warning: leaving out %s: it is not signed\n' "$rpm" >&2
                continue
                ;;
            # More likely a wrong key file than an earlier release, which prune leaves out.
            "other key") die "$rpm is signed by a key not in the key file" ;;
            *) die "unexpected signature state: $sig" ;;
        esac
        # The name goes into the bundle's file names.
        [[ $pkg =~ ^[A-Za-z0-9._+-]+$ ]] || die "$rpm has a name dnf-repo.sh can't use: $pkg"
        [[ -z $name || $name == "$pkg" ]] || die "$rpm is not a package of $name"
        name=$pkg
        mkdir -p "$work/packages/$tag"
        cp -- "$rpm" "$work/packages/$tag/"
        count=$((count + 1))
    done
    ((count > 0)) || die "no signed RPMs in $rpmdir/vX.Y.Z/"

    createrepo_c --quiet --location-prefix "$url" --outputdir "$work/bundle" \
        "$work/packages" >&2
    local repodata=$work/bundle/repodata file
    if [[ -n $previous ]]; then
        # A client that read the previous repomd.xml just before a deploy fetches the files it
        # names just after; they must still be there, or dnf gets a 404 and skips the repository.
        mkdir "$work/previous"
        tar -xzf "$previous" -C "$work/previous" repodata/repomd.xml ||
            die "$previous has no repodata/repomd.xml"
        while IFS= read -r file; do
            [[ -e $repodata/$file ]] ||
                tar -xzf "$previous" -C "$work/bundle" "repodata/$file" ||
                die "$previous has no repodata/$file, which its repomd.xml names"
        done < <(sed -n 's|.*<location href="repodata/\([^"/]*\)".*|\1|p' \
            "$work/previous/repodata/repomd.xml")
    fi
    # One signature: dnf5 can't parse a repomd.xml.asc that holds two.
    gpg --batch --armor --detach-sign --local-user "$fingerprint" \
        --output "$repodata/repomd.xml.asc" "$repodata/repomd.xml"
    cp -- "$keyfile" "$work/bundle/RPM-GPG-KEY-$name"

    mkdir -p -- "$outdir"
    tar -czf "$outdir/$name-dnf-repo.tar.gz" -C "$work/bundle" repodata "RPM-GPG-KEY-$name"
    printf '%s\n' "$outdir/$name-dnf-repo.tar.gz"
)

prune() (
    (($# == 2)) || usage
    local keyfile=$1 rpmdir=$2 work rpm sig
    [[ -f $keyfile ]] || die "no such key file: $keyfile"
    [[ -d $rpmdir ]] || die "no such directory: $rpmdir"
    work=$(mktemp -d)
    trap 'rm -rf -- "$work"' EXIT
    import_keys "$work/keyring" "$keyfile"
    shopt -s nullglob
    for rpm in "$rpmdir"/*/*.rpm; do
        sig=$(signature "$rpm" "$work/keyring")
        case $sig in
            signed | unsigned) ;;
            "other key")
                printf 'dnf-repo.sh: warning: leaving out %s: it is signed by a key not in %s\n' \
                    "$rpm" "$keyfile" >&2
                rm -- "$rpm"
                ;;
            *) die "unexpected signature state: $sig" ;;
        esac
    done
)

fingerprint() {
    (($# == 0)) || usage
    local keys fingerprints
    keys=$(gpg --batch --with-colons --list-secret-keys 2>&1) ||
        die "can't list the secret keys: $keys"
    fingerprints=$(primary_fingerprints <<<"$keys")
    [[ $fingerprints =~ ^[0-9A-F]{40}$ ]] || die "the keyring must hold one secret key"
    printf '%s\n' "$fingerprints"
}

(($# > 0)) || usage
mode=$1
shift
case $mode in
    sign) sign "$@" ;;
    metadata) metadata "$@" ;;
    prune) prune "$@" ;;
    fingerprint) fingerprint "$@" ;;
    *) usage ;;
esac
