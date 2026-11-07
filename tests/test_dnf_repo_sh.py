"""Tests for `packaging/dnf-repo.sh`'s checks on what it signs and indexes.

The script runs with stub `rpm`, `rpmkeys`, `rpmsign`, `createrepo_c` and `gpg`
first on `PATH`, so no rpm tools are needed. A stub RPM is a text file holding
its name, version and signing key: ``-`` for none as rpm 6 reports it, ``-4``
for none as rpm 4 does (passing the check), ``bad`` for a bad signature and
``damaged`` for an unsigned package whose digests don't match. The stub
`rpmkeys` prints the RPM's path before its checks, as the real one does. A key
file holds one key per line. The stub `createrepo_c` writes a primary.xml that
lists each package's location, and the stub `gpg` writes the signing key into
the signature and lists a key file's keys. ci.yml's dnf-repo job runs the real
tools.
"""

import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "dnf-repo.sh"
SIGNER = "0123456789ABCDEF0123456789ABCDEF01234567"
OTHER = "89ABCDEF0123456789ABCDEF0123456789ABCDEF"
URL = "https://github.com/ORG/REPO/releases/download/"
USAGE = """\
dnf-repo.sh: usage: packaging/dnf-repo.sh sign FINGERPRINT RPM
       packaging/dnf-repo.sh metadata FINGERPRINT KEYFILE URL RPMDIR OUTDIR [PREVIOUS]
"""

STUBS = {
    "rpm": """\
import sys
name, version, _ = open(sys.argv[-1]).read().split()
print(name, version, end="")
""",
    "rpmkeys": """\
import pathlib, sys
args = sys.argv[1:]
keys = pathlib.Path(args[args.index("--dbpath") + 1]) / "keys"
if "--import" in args:
    keys.write_text(pathlib.Path(args[-1]).read_text())
    sys.exit(0)
known = keys.read_text().split()
_, _, signer = open(args[-1]).read().split()
if "--nosignature" in args:
    sys.exit(1 if signer == "damaged" else 0)
print(f"{args[-1]}:")
if signer == "damaged":
    print("    Payload SHA256 digest: BAD")
    sys.exit(1)
if signer == "-4":
    print("    Header SHA256 digest: OK")
    sys.exit(0)
if signer == "-":
    print("    Header OpenPGP RSA signature: NOTFOUND")
    sys.exit(1)
if signer == "bad":
    print("    Header OpenPGP V4 RSA/SHA512 signature, key fingerprint: abc: BAD")
    sys.exit(1)
if signer not in known:
    print(f"    Header OpenPGP V4 RSA/SHA512 signature, key ID {signer}: NOKEY")
    sys.exit(1)
print(f"    Header OpenPGP V4 RSA/SHA512 signature, key fingerprint: {signer}: OK")
""",
    "rpmsign": """\
import sys
macros = dict(a.split() for a in sys.argv if a.startswith("_"))
signer = macros["_openpgp_sign_id"]
if macros["_gpg_name"] != signer:
    sys.exit(1)
name, version, _ = open(sys.argv[-1]).read().split()
open(sys.argv[-1], "w").write(f"{name} {version} {signer}")
""",
    "createrepo_c": """\
import pathlib, sys
args = sys.argv[1:]
prefix = args[args.index("--location-prefix") + 1]
packages = pathlib.Path(args[-1])
repodata = pathlib.Path(args[args.index("--outputdir") + 1]) / "repodata"
repodata.mkdir(parents=True)
hrefs = sorted(prefix + str(p.relative_to(packages)) for p in packages.rglob("*.rpm"))
(repodata / "new-primary.xml").write_text("\\n".join(hrefs))
(repodata / "repomd.xml").write_text('<location href="repodata/new-primary.xml"/>\\n')
""",
    "gpg": """\
import sys
args = sys.argv[1:]
if "--show-keys" in args:
    for key in open(args[-1]).read().split():
        print(f"fpr:::::::::{key}:")  # codespell:ignore fpr
    sys.exit(0)
signer = args[args.index("--local-user") + 1]
open(args[args.index("--output") + 1], "w").write(signer)
""",
}


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in STUBS.items():
        stub = bin_dir / name
        stub.write_text(f"#!{sys.executable}\n{text}", encoding="utf-8")
        stub.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


@pytest.fixture
def keyfile(tmp_path: Path) -> Path:
    path = tmp_path / "RPM-GPG-KEY"
    path.write_text(f"{SIGNER}\n", encoding="utf-8")
    return path


def run(env: dict[str, str], *args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- fixed script, test-owned arguments
        [str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=False, env=env
    )


def add_rpm(rpmdir: Path, tag: str, version: str, signer: str, name: str = "app") -> Path:
    path = rpmdir / tag / f"{name}.noarch.rpm"
    path.parent.mkdir(parents=True)
    path.write_text(f"{name} {version} {signer}", encoding="utf-8")
    return path


def metadata(
    env: dict[str, str], tmp_path: Path, keyfile: Path, *previous: Path
) -> subprocess.CompletedProcess[str]:
    return run(
        env, "metadata", SIGNER, keyfile, URL, tmp_path / "rpms", tmp_path / "out", *previous
    )


def write_bundle(path: Path, files: dict[str, str]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, text in files.items():
            data = text.encode()
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return path


def bundle_files(path: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            data = tar.extractfile(member)
            if data is not None:
                files[member.name] = data.read().decode()
    return files


@pytest.mark.parametrize(
    "args",
    [
        pytest.param([], id="no mode"),
        pytest.param(["publish"], id="unknown mode"),
        pytest.param(["sign", SIGNER], id="sign without RPM"),
        pytest.param(["sign", SIGNER, "a.rpm", "b.rpm"], id="sign with two RPMs"),
        pytest.param(["metadata", SIGNER, "KEY", URL, "rpms"], id="metadata without OUTDIR"),
        pytest.param(
            ["metadata", SIGNER, "KEY", URL, "rpms", "out", "prev", "x"], id="metadata, extra"
        ),
    ],
)
def test_bad_arguments_exit_1_with_usage(env: dict[str, str], args: list[str]) -> None:
    result = run(env, *args)
    assert result.returncode == 1
    assert result.stderr == USAGE


@pytest.mark.parametrize("mode", ["sign", "metadata"])
@pytest.mark.parametrize(
    "fingerprint", ["01234567", f"{SIGNER}0", "user@example.com", f"{SIGNER[:-1]}G"]
)
def test_a_key_is_named_by_its_full_fingerprint(
    env: dict[str, str], tmp_path: Path, keyfile: Path, mode: str, fingerprint: str
) -> None:
    rpm = add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", "-")
    args = [rpm] if mode == "sign" else [keyfile, URL, tmp_path / "rpms", tmp_path / "out"]
    result = run(env, mode, fingerprint, *args)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: not a key fingerprint (40 hex digits): {fingerprint}\n"


def test_sign_signs_the_rpm_in_place_with_the_key(env: dict[str, str], tmp_path: Path) -> None:
    rpm = add_rpm(tmp_path, "v1.0.0rc1", "1.0.0~rc1", "-")
    result = run(env, "sign", SIGNER, rpm)
    assert result.returncode == 0, result.stderr
    assert rpm.read_text(encoding="utf-8") == f"app 1.0.0~rc1 {SIGNER}"


def test_sign_fails_on_a_missing_rpm(env: dict[str, str], tmp_path: Path) -> None:
    result = run(env, "sign", SIGNER, tmp_path / "missing.rpm")
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: no such RPM: {tmp_path / 'missing.rpm'}\n"


def test_metadata_indexes_each_release_at_its_download_url(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    result = metadata(env, tmp_path, keyfile)
    bundle = tmp_path / "out" / "app-dnf-repo.tar.gz"
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{bundle}\n"
    files = bundle_files(bundle)
    assert files["repodata/new-primary.xml"] == (
        f"{URL}v1.0.0/app.noarch.rpm\n{URL}v1.1.0/app.noarch.rpm"
    )
    assert files["repodata/repomd.xml.asc"] == SIGNER
    assert files["RPM-GPG-KEY-app"] == f"{SIGNER}\n"


@pytest.mark.parametrize(
    "unsigned", [pytest.param("-", id="rpm 6"), pytest.param("-4", id="rpm 4")]
)
def test_metadata_leaves_out_an_unsigned_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path, unsigned: str
) -> None:
    rpm = add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", unsigned)
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 0, result.stderr
    assert result.stderr == f"dnf-repo.sh: warning: leaving out {rpm}: it is not signed\n"
    files = bundle_files(tmp_path / "out" / "app-dnf-repo.tar.gz")
    assert files["repodata/new-primary.xml"] == f"{URL}v1.1.0/app.noarch.rpm"


def test_metadata_does_not_read_the_rpms_path_as_a_signature(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    rpmdir = tmp_path / "Signature, key x"
    rpm = add_rpm(rpmdir, "v1.0.0", "1.0.0", "-4")
    add_rpm(rpmdir, "v1.1.0", "1.1.0", SIGNER)
    result = run(env, "metadata", SIGNER, keyfile, URL, rpmdir, tmp_path / "out")
    assert result.returncode == 0, result.stderr
    assert result.stderr == f"dnf-repo.sh: warning: leaving out {rpm}: it is not signed\n"


@pytest.mark.parametrize("signer", [pytest.param(OTHER, id="other key"), "bad"])
def test_metadata_fails_on_a_signature_it_cannot_verify(
    env: dict[str, str], tmp_path: Path, keyfile: Path, signer: str
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", signer)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr.startswith(
        f"dnf-repo.sh: {rpm} has a signature by a key not in the key file, or a bad one:\n"
    )
    assert not (tmp_path / "out").exists()


def test_metadata_fails_on_a_damaged_unsigned_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", "damaged")
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr.startswith(f"dnf-repo.sh: {rpm} is damaged:\n")
    assert not (tmp_path / "out").exists()


def test_metadata_accepts_a_lowercase_fingerprint(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    result = run(env, "metadata", SIGNER.lower(), keyfile, URL, tmp_path / "rpms", tmp_path / "out")
    assert result.returncode == 0, result.stderr
    files = bundle_files(tmp_path / "out" / "app-dnf-repo.tar.gz")
    assert files["repodata/repomd.xml.asc"] == SIGNER.lower()


def test_metadata_accepts_any_key_in_the_key_file(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    keyfile.write_text(f"{OTHER}\n{SIGNER}\n", encoding="utf-8")
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", OTHER)
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 0, result.stderr


def test_metadata_refuses_a_pre_release(env: dict[str, str], tmp_path: Path, keyfile: Path) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    rpm = add_rpm(tmp_path / "rpms", "v2.0.0rc1", "2.0.0~rc1", SIGNER)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {rpm} is a pre-release (2.0.0~rc1)\n"
    assert not (tmp_path / "out").exists()


def test_metadata_refuses_an_rpm_under_another_releases_tag(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    rpm = add_rpm(tmp_path / "rpms", "v1.2.0", "1.1.0", SIGNER)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {rpm} is version 1.1.0, not 1.2.0\n"
    assert not (tmp_path / "out").exists()


def test_metadata_refuses_two_package_names(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER, name="other")
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {rpm} is not a package of app\n"


def test_metadata_refuses_a_name_it_cannot_put_in_a_file_name(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    rpm = add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    rpm.write_text(f"../app 1.0.0 {SIGNER}", encoding="utf-8")
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {rpm} has a name dnf-repo.sh can't use: ../app\n"
    assert not (tmp_path / "out").exists()


def test_metadata_takes_the_name_from_signed_rpms_only(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", "-", name="old")
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{tmp_path / 'out' / 'app-dnf-repo.tar.gz'}\n"


def test_metadata_fails_with_no_signed_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", "-")
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr.endswith(f"dnf-repo.sh: no signed RPMs in {tmp_path / 'rpms'}/vX.Y.Z/\n")


def test_metadata_needs_a_url_that_ends_in_a_slash(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    result = run(
        env, "metadata", SIGNER, keyfile, URL.rstrip("/"), tmp_path / "rpms", tmp_path / "out"
    )
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: the URL must end in /: {URL.rstrip('/')}\n"


def test_metadata_keeps_the_files_the_previous_repomd_names(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    previous = write_bundle(
        tmp_path / "previous.tar.gz",
        {
            "repodata/repomd.xml": '<location href="repodata/old-primary.xml"/>\n',
            "repodata/repomd.xml.asc": "old signature",
            "repodata/old-primary.xml": "old primary",
            "repodata/older-primary.xml": "kept by the bundle before",
        },
    )
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    result = metadata(env, tmp_path, keyfile, previous)
    assert result.returncode == 0, result.stderr
    files = bundle_files(tmp_path / "out" / "app-dnf-repo.tar.gz")
    assert files["repodata/old-primary.xml"] == "old primary"
    assert "repodata/older-primary.xml" not in files
    assert files["repodata/repomd.xml"] == '<location href="repodata/new-primary.xml"/>\n'
    assert files["repodata/repomd.xml.asc"] == SIGNER


@pytest.mark.parametrize(
    ("files", "error"),
    [
        pytest.param(
            {"repodata/primary.xml": ""}, "has no repodata/repomd.xml", id="no repomd.xml"
        ),
        pytest.param(
            {"repodata/repomd.xml": '<location href="repodata/old-primary.xml"/>\n'},
            "has no repodata/old-primary.xml, which its repomd.xml names",
            id="a file repomd.xml names is missing",
        ),
    ],
)
def test_metadata_fails_on_an_incomplete_previous_bundle(
    env: dict[str, str], tmp_path: Path, keyfile: Path, files: dict[str, str], error: str
) -> None:
    previous = write_bundle(tmp_path / "previous.tar.gz", files)
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    result = metadata(env, tmp_path, keyfile, previous)
    assert result.returncode == 1
    assert result.stderr.endswith(f"dnf-repo.sh: {previous} {error}\n")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("missing", ["keyfile", "previous"])
def test_metadata_fails_on_a_missing_input(
    env: dict[str, str], tmp_path: Path, keyfile: Path, missing: str
) -> None:
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    path = tmp_path / "missing"
    if missing == "keyfile":
        result = metadata(env, tmp_path, path)
        error = f"no such key file: {path}"
    else:
        result = metadata(env, tmp_path, keyfile, path)
        error = f"no such bundle: {path}"
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {error}\n"
    assert not (tmp_path / "out").exists()


def test_metadata_fails_when_the_key_file_lacks_the_signing_key(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    keyfile.write_text(f"{OTHER}\n", encoding="utf-8")
    add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", OTHER)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {keyfile} doesn't hold the key {SIGNER}\n"
    assert not (tmp_path / "out").exists()


def test_metadata_fails_on_a_file_that_is_not_an_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", SIGNER)
    rpm.write_text("not an rpm at all", encoding="utf-8")
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr.endswith(f"dnf-repo.sh: not an RPM: {rpm}\n")
    assert not (tmp_path / "out").exists()
