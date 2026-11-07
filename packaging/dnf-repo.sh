#!/usr/bin/env bash
# Signs RPMs, and builds the signed dnf repository metadata for RPMs a GitHub Release holds.
# Needs rpm, rpmsign, rpmkeys, createrepo_c, gpg and tar, as the Fedora container in ci.yml's
# dnf-repo job has. gpg signs with the secret key FINGERPRINT from its keyring
# ($GNUPGHOME), which must have no passphrase.
#
# Usage:
#   packaging/dnf-repo.sh sign FINGERPRINT RPM
#     Signs RPM in place with the key FINGERPRINT.
#   packaging/dnf-repo.sh metadata FINGERPRINT KEYFILE URL RPMDIR OUTDIR [PREVIOUS]
#     Indexes RPMDIR/vX.Y.Z/NAME.noarch.rpm for each release, with each package's
#     location URL as URL, which ends in /, then vX.Y.Z/NAME.noarch.rpm. Writes
#     OUTDIR/NAME-dnf-repo.tar.gz, holding repodata/ with repomd.xml signed by
#     FINGERPRINT, and KEYFILE as RPM-GPG-KEY-NAME, and prints its path. PREVIOUS is the
#     bundle this replaces, if any.
set -euo pipefail

die() {
    printf 'dnf-repo.sh: %s\n' "$*" >&2
    exit 1
}

usage() {
    die "usage: packaging/dnf-repo.sh sign FINGERPRINT RPM
       packaging/dnf-repo.sh metadata FINGERPRINT KEYFILE URL RPMDIR OUTDIR [PREVIOUS]"
}

# A full fingerprint, so gpg can't pick another key whose ID or user ID matches.
check_fingerprint() {
    [[ $1 =~ ^[0-9A-Fa-f]{40}$ ]] || die "not a key fingerprint (40 hex digits): $1"
}

sign() {
    (($# == 2)) || usage
    check_fingerprint "$1"
    [[ -f $2 ]] || die "no such RPM: $2"
    # rpm 6 reads _openpgp_sign_id, rpm 4 _gpg_name.
    rpmsign --addsign --define "_openpgp_sign_id $1" --define "_gpg_name $1" -- "$2" >&2
}

# Prints "signed" when RPM $1 has signatures and each verifies with a key in the keyring
# database $2, "unsigned" when it has none, and fails otherwise.
signature() {
    local out status=0
    out=$(rpmkeys --dbpath "$2" -Kv -- "$1" 2>&1) || status=$?
    # rpmkeys names the key of each signature it finds ("Signature, key" in rpm 4). With
    # none, rpm 6 fails the check and rpm 4 passes it, so the status alone can't tell. The
    # match skips the first line, the RPM's path, which could hold the same text.
    if [[ ${out#*$'\n'} == *[Ss]"ignature, key "* ]]; then
        ((status == 0)) || die "$1 has a signature by a key not in the key file, or a bad one:
$out"
        echo signed
        return
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
    [[ -f $keyfile ]] || die "no such key file: $keyfile"
    # Users check repomd.xml against KEYFILE: signed by another key, dnf skips the
    # repository with only a warning. gpg lists fingerprints in uppercase.
    local keys
    keys=$(gpg --batch --with-colons --show-keys -- "$keyfile" 2>&1) ||
        die "can't read the keys in $keyfile: $keys"
    [[ $keys == *":$(printf '%s' "$fingerprint" | tr a-f A-F):"* ]] ||
        die "$keyfile doesn't hold the key $fingerprint"
    [[ $url == */ ]] || die "the URL must end in /: $url"
    [[ -z $previous || -f $previous ]] || die "no such bundle: $previous"

    local work
    work=$(mktemp -d)
    trap 'rm -rf -- "$work"' EXIT
    mkdir "$work/keyring" "$work/packages" "$work/bundle"
    rpmkeys --dbpath "$work/keyring" --import "$keyfile" ||
        die "can't read the keys in $keyfile"

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
        if [[ $sig == unsigned ]]; then
            # Releases made before the project signed its RPMs.
            printf 'dnf-repo.sh: warning: leaving out %s: it is not signed\n' "$rpm" >&2
            continue
        fi
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

(($# > 0)) || usage
mode=$1
shift
case $mode in
    sign) sign "$@" ;;
    metadata) metadata "$@" ;;
    *) usage ;;
esac
