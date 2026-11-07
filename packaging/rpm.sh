#!/usr/bin/env bash
# Builds the RPM of the commit checked out, as VERSION, from packaging/rpm.spec at that
# commit, into OUTDIR/NAME.noarch.rpm (NAME is the spec's Name), and prints that path.
# Needs git and rpmbuild, as .github/workflows/rpm.yml's Fedora container has.
# Usage: packaging/rpm.sh VERSION OUTDIR
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
readonly root

die() {
    printf 'rpm.sh: %s\n' "$*" >&2
    exit 1
}

# git refuses a repository another user owns, as a checkout mounted into a container is.
git() {
    command git -C "$root" -c safe.directory="$root" "$@"
}

(($# == 2)) || die "usage: packaging/rpm.sh VERSION OUTDIR"
# RPM sorts 1.2.0rc1 after 1.2.0, so a pre-release must carry its - for the ~ below.
[[ $1 =~ ^[0-9]+(\.[0-9]+)*(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?$ ]] ||
    die "not a version: $1 (write X.Y.Z, or X.Y.Z-rc.N for a pre-release)"
# RPM's Version can't hold a -; ~ takes its place and, like SemVer's -, sorts before the
# release.
version=${1//-/\~} outdir=$2

# The commit's time as build time and file times, and a fixed build host, so a rebuild
# of the same commit in the same image gives the same bytes.
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct HEAD)
export SOURCE_DATE_EPOCH

work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mkdir "$work/SOURCES"
git show HEAD:packaging/rpm.spec >"$work/rpm.spec"
define=(--define "tag_version $version" --define "_topdir $work"
    --define "use_source_date_epoch_as_buildtime 1" --define "_buildhost reproducible")
name=$(rpmspec -q --srpm --qf '%{NAME}' "${define[@]}" "$work/rpm.spec")
git archive --format=tar.gz --prefix="$name-$version/" \
    -o "$work/SOURCES/$name-$version.tar.gz" HEAD
# stdout carries only the path printed below.
rpmbuild -bb "${define[@]}" "$work/rpm.spec" >&2
built=("$work/RPMS/noarch/$name-$version"-*.noarch.rpm)
[[ -f ${built[0]} && ${#built[@]} == 1 ]] || die "expected one noarch RPM of $name $version"
mkdir -p -- "$outdir"
cp -- "${built[0]}" "$outdir/$name.noarch.rpm"
printf '%s\n' "$outdir/$name.noarch.rpm"
