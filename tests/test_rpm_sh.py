"""Tests for `packaging/rpm.sh`'s version check, which decides the RPM's version.

The script runs as `rpm.yml` runs it, with stub `rpmspec` and `rpmbuild` first on
`PATH`, so no rpm tools are needed: the stub `rpmbuild` writes the version the
script defines into the RPM file it makes.
"""

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "rpm.sh"

STUBS = {
    "rpmspec": "#!/bin/sh\nprintf app\n",
    "rpmbuild": """\
#!/usr/bin/env bash
for arg; do
    case $arg in
        "tag_version "*) version=${arg#* } ;;
        "_topdir "*) topdir=${arg#* } ;;
    esac
done
mkdir -p "$topdir/RPMS/noarch"
printf '%s' "$version" >"$topdir/RPMS/noarch/app-$version-1.noarch.rpm"
""",
}


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in STUBS.items():
        stub = bin_dir / name
        stub.write_text(text, encoding="utf-8")
        stub.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- fixed script, test-owned arguments
        [str(SCRIPT), *args], capture_output=True, text=True, check=False, env=env
    )


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        pytest.param("1.2.0", "1.2.0", id="release"),
        pytest.param("1.2.0rc1", "1.2.0~rc1", id="pep440 rc"),
        pytest.param("1.2.0a1", "1.2.0~a1", id="pep440 alpha"),
        pytest.param("1.2.0b2", "1.2.0~b2", id="pep440 beta"),
        pytest.param("1.2.0-rc.1", "1.2.0~rc.1", id="semver rc"),
        pytest.param("1.2.0-alpha", "1.2.0~alpha", id="semver alpha"),
    ],
)
def test_rpm_version_has_a_tilde_before_the_pre_release(
    env: dict[str, str], tmp_path: Path, version: str, expected: str
) -> None:
    result = run(env, version, str(tmp_path / "out"))
    rpm = tmp_path / "out" / "app.noarch.rpm"
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{rpm}\n"
    assert rpm.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize(
    "version",
    [
        pytest.param("1.2.0-1", id="pep440 implicit post"),
        pytest.param("1.2.0-post.1", id="pep440 post"),
        pytest.param("1.2.0-Rev2", id="pep440 rev"),
        pytest.param("1.2.0-r.1", id="pep440 r"),
        pytest.param("1.2.0.dev3", id="pep440 dev"),
        pytest.param("1.2.0rc1.dev2", id="pep440 rc dev"),
        pytest.param("1.2.0-dev3", id="pep440 dev after -"),
        pytest.param("1.2.0-rc1.dev2", id="pep440 rc dev after -"),
        pytest.param("1.2.0-RC1DEV2", id="pep440 rc dev unseparated"),
        pytest.param("1.2.0+build", id="build metadata"),
        pytest.param("v1.2.0", id="leading v"),
        pytest.param("1;id", id="shell"),
        pytest.param("", id="empty"),
    ],
)
def test_other_versions_are_refused_before_building(
    env: dict[str, str], tmp_path: Path, version: str
) -> None:
    result = run(env, version, str(tmp_path / "out"))
    assert result.returncode == 1
    assert result.stderr.startswith(f"rpm.sh: not a version: {version} (")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("args", [[], ["1.2.0"], ["1.2.0", "out", "extra"]])
def test_bad_arguments_exit_1_with_usage(env: dict[str, str], args: list[str]) -> None:
    result = run(env, *args)
    assert result.returncode == 1
    assert result.stderr == "rpm.sh: usage: packaging/rpm.sh VERSION OUTDIR\n"
