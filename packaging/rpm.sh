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
outdir=$2
# RPM sorts 1.2.0rc1 after 1.2.0 and can't hold a - in a version. A ~ before the
# pre-release part sorts it before the release, as PEP 440 and SemVer do.
release='[0-9]+(\.[0-9]+)*'
# PEP 440's version pattern, which release.yml reads before SemVer's (in lowercase, without
# epoch or local part).
pre='([-_.]?(a|b|c|rc|alpha|beta|pre|preview)[-_.]?[0-9]*)?'
post='(-[0-9]+|[-_.]?(post|rev|r)[-_.]?[0-9]*)?'
dev='([-_.]?dev[-_.]?[0-9]*)?'
pep440="^$release$pre$post$dev\$"
# Whether PEP 440 reads $1 as a post-release of a release (1.2.0-post.1, sorted after
# 1.2.0) or as a development release (1.2.0-dev3, sorted before 1.2.0-alpha). With a ~,
# RPM would sort it the other way, so dnf would skip an upgrade.
post_or_dev() {
    local lower
    # Not ${1,,}, which macOS's bash 3.2 lacks.
    lower=$(tr '[:upper:]' '[:lower:]' <<<"$1")
    # Groups: 2 is the pre-release, 4 the post-release, 6 the development release.
    [[ $lower =~ $pep440 ]] &&
        [[ -n ${BASH_REMATCH[6]} || (-n ${BASH_REMATCH[4]} && -z ${BASH_REMATCH[2]}) ]]
}
if [[ $1 =~ ^($release)((a|b|rc)[0-9]+)$ ]]; then
    version="${BASH_REMATCH[1]}~${BASH_REMATCH[3]}"
elif [[ $1 =~ ^$release(-[A-Za-z][0-9A-Za-z]*(\.[0-9A-Za-z]+)*)?$ ]] && ! post_or_dev "$1"; then
    version=${1/-/\~}
else
    die "not a version: $1 (write X.Y.Z, or X.Y.ZrcN or X.Y.Z-rc.N for a pre-release)"
fi

# The commit's time as build time and file times, and a fixed build host, so a rebuild
# of the same commit in the same image, with the same rpm-build, gives the same bytes.
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
