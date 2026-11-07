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

# Prints the RPM version of the tag's version $1, or fails when $1 is not a form it takes.
# RPM sorts 1.2.0rc1 after 1.2.0 and can't hold a - in a version, so a ~ goes before the
# pre-release part, which RPM sorts before the release. Every version taken gets a ~
# exactly when release.yml reads it as a pre-release.
rpm_version() {
    local n='(0|[1-9][0-9]*)'
    local numbers="$n\.$n\.$n"
    # SemVer's pre-release, in lowercase, without hyphens and led by a letter. RPM sorts
    # letters in ASCII order, so 1.2.0~RC.1 would sort before 1.2.0~beta.1.
    local semver='[a-z][0-9a-z]*(\.(0|[1-9][0-9]*|[0-9]*[a-z][0-9a-z]*))*'
    [[ $1 =~ ^$numbers((a|b|rc)[0-9]+|-$semver)?$ ]] || return 1
    # PEP 440, which release.yml reads before SemVer, reads 1.2.0-dev3 as a development
    # release, sorted before 1.2.0-alpha, and 1.2.0-post.1 as a post-release, sorted after
    # 1.2.0. With a ~, RPM would sort each the other way, so dnf would skip an upgrade.
    local pre='([-_.]?(a|b|c|rc|alpha|beta|pre|preview)[-_.]?[0-9]*)?'
    local post='(-[0-9]+|[-_.]?(post|rev|r)[-_.]?[0-9]*)'
    local dev='[-_.]?dev[-_.]?[0-9]*'
    if [[ $1 =~ ^$numbers$pre$post?$dev$ || $1 =~ ^$numbers$post$ ]]; then
        return 1
    fi
    local base=${1%%[!0-9.]*}
    local pre_release=${1#"$base"}
    if [[ -z $pre_release ]]; then
        printf '%s\n' "$1"
    else
        printf '%s~%s\n' "$base" "${pre_release#-}"
    fi
}

(($# == 2)) || die "usage: packaging/rpm.sh VERSION OUTDIR"
outdir=$2
version=$(rpm_version "$1") ||
    die "not a version: $1 (write X.Y.Z, or X.Y.ZrcN or X.Y.Z-rc.N for a pre-release)"

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
