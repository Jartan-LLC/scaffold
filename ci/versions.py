"""Tell a release from a pre-release, and order releases, for the release workflows.

A tag's version may be written under PEP 440 or SemVer. A version both schemes
accept is read as PEP 440, as PyPI reads it.

`release_notes.py --prerelease` uses this for `release.yml`, and
`publish-docker.yml` runs ``versions.py --image-tags VERSION``, with the
repository's tags on stdin, one per line, to choose the image's tags. That
prints lines for ``$GITHUB_OUTPUT``: ``version``, the version as written up to
any ``+``; ``minor``, ``X.Y`` for a release and empty for a pre-release; and
``latest``, ``true`` when no tag is a higher release. Standard library only,
so the workflows need nothing but the runner's ``python3``.
"""

import re
import sys
from collections.abc import Iterable
from typing import NamedTuple

# PEP 440's own pattern (its Appendix B), without the leading `v` the tag loses.
_PEP_440 = re.compile(
    r"""
    (?:(?P<epoch>[0-9]+)!)?
    (?P<release>[0-9]+(?:\.[0-9]+)*)
    (?P<pre>[-_.]?(?P<pre_l>a|b|c|rc|alpha|beta|pre|preview)[-_.]?(?P<pre_n>[0-9]+)?)?
    (?P<post>(?:-(?P<post_n1>[0-9]+))|(?:[-_.]?(?P<post_l>post|rev|r)[-_.]?(?P<post_n2>[0-9]+)?))?
    (?P<dev>[-_.]?(?P<dev_l>dev)[-_.]?(?P<dev_n>[0-9]+)?)?
    (?:\+(?P<local>[a-z0-9]+(?:[-_.][a-z0-9]+)*))?
    """,
    re.VERBOSE | re.IGNORECASE,
)
# The pattern semver.org gives for SemVer 2.0.0.
_SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?"
)
# The characters and length Docker allows in an image tag.
_DOCKER_TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")

type ReleaseKey = tuple[int, tuple[int, ...], int]


class _Version(NamedTuple):
    prerelease: bool
    # Leaves out the pre-release and development parts, so it orders releases only.
    key: ReleaseKey


def _read(version: str) -> _Version | None:
    """Read ``version`` as PEP 440, else as SemVer, as PyPI reads a version both accept.

    Args:
        version: The version without the tag's leading ``v``.

    Returns:
        Whether it is a pre-release, and its key; None for a string that is no
        version.
    """
    if pep_440 := _PEP_440.fullmatch(version):
        prerelease = bool(pep_440["pre"] or pep_440["dev"])
        epoch = int(pep_440["epoch"] or 0)
        numbers = [int(n) for n in pep_440["release"].split(".")]
        post = -1 if pep_440["post"] is None else int(pep_440["post_n1"] or pep_440["post_n2"] or 0)
    elif semver := _SEMVER.fullmatch(version):
        prerelease = bool(semver["prerelease"])
        epoch, numbers, post = 0, [int(n) for n in semver.groups()[:3]], -1
    else:
        return None
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()
    return _Version(prerelease, (epoch, tuple(numbers), post))


def is_prerelease(version: str) -> bool:
    """Return whether ``version`` is a pre-release under PEP 440 or SemVer.

    A version both schemes accept is read as PEP 440, as PyPI reads it, so
    ``1.2.0-1`` is a post-release there and not a pre-release.

    Args:
        version: The version without the tag's leading ``v``.

    Returns:
        True for a PEP 440 pre-release or development release (``1.2.0rc1``,
        ``1.2.0.dev3``) or a SemVer pre-release (``1.2.0-alpha.1``).
    """
    read = _read(version)
    return read is not None and read.prerelease


def _release_key(version: str) -> ReleaseKey | None:
    """Return a key that orders releases as PEP 440 does.

    Versions PEP 440 calls equal get equal keys: ``1.2`` and ``1.2.0``, or
    ``1.2.0-1`` and ``1.2.0.post1``. A local version (``+build.5``) is ignored.

    Args:
        version: The version without the tag's leading ``v``.

    Returns:
        The epoch, the release numbers without trailing zeros, and the
        post-release number or -1; None for a pre-release or a string that is
        no version.
    """
    read = _read(version)
    return None if read is None or read.prerelease else read.key


def image_tags(version: str, tags: Iterable[str]) -> dict[str, str]:
    """Return ``publish-docker.yml``'s outputs for ``version``.

    Args:
        version: The pushed tag's version, without its ``v``.
        tags: The repository's tag names, ``v`` included; names that hold no
            version are ignored.

    Returns:
        ``version`` as written up to any ``+``; ``minor``, the release's
        first two numbers, or empty for a pre-release; and ``latest``,
        ``true`` when no tag is a higher release.

    Raises:
        ValueError: ``version`` is neither a PEP 440 nor a SemVer version, or
            makes no valid Docker tag (an epoch's ``!``).
    """
    read = _read(version)
    if read is None:
        raise ValueError(f"v{version} is neither a PEP 440 nor a SemVer version")
    # A Docker tag can't hold a `+`, so the build metadata or local part goes.
    docker_version = version.partition("+")[0]
    # metadata-action would replace a character a tag can't hold, pushing another name.
    if not _DOCKER_TAG.fullmatch(docker_version):
        raise ValueError(f"v{version} makes no valid Docker tag")
    if read.prerelease:
        return {"version": docker_version, "minor": "", "latest": "false"}
    keys = (_release_key(name.removeprefix("v")) for name in tags)
    highest = max((k for k in keys if k is not None), default=read.key)
    major, minor = (*read.key[1], 0)[:2]
    return {
        "version": docker_version,
        "minor": f"{major}.{minor}",
        "latest": str(read.key >= highest).lower(),
    }


def main(argv: list[str]) -> int:
    """Print ``publish-docker.yml``'s outputs, reading the tags from stdin.

    Args:
        argv: ``--image-tags`` and the pushed tag's version, without its ``v``.

    Returns:
        The exit status: 0; 1 when the version is no PEP 440 or SemVer
        version or makes no valid Docker tag, with nothing printed; 2 for bad
        arguments.
    """
    match argv:
        case ["--image-tags", version]:
            try:
                outputs = image_tags(version, sys.stdin.read().split())
            except ValueError as error:
                sys.stderr.write(f"::error::{error}, so the image gets no tags\n")
                return 1
        case _:
            sys.stderr.write("usage: versions.py --image-tags VERSION\n")
            return 2
    if outputs["latest"] == "false":
        why = "is a pre-release" if is_prerelease(version) else "is not the highest release"
        sys.stderr.write(f"::notice::v{version} {why}; leaving :latest alone\n")
    sys.stdout.writelines(f"{name}={value}\n" for name, value in outputs.items())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
