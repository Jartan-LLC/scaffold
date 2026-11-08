"""Tests for `packaging/dnf-repo.sh`'s checks on what it signs and indexes.

The script runs with stub `rpm`, `rpmkeys`, `rpmsign`, `createrepo_c` and `gpg`
first on `PATH`, so no rpm tools are needed. A stub RPM is a text file holding
its name, version and signing key: ``-`` for none as rpm 6 reports it, ``-4``
for none as rpm 4 does (passing the check), ``bad`` for a bad signature,
``damaged`` for an unsigned package whose digests don't match, a key and
``-damaged`` for a package that key signed whose digests don't match, and a key
and ``+bad`` for a package that key signed that also has a bad signature. The
stub `rpmkeys` prints the RPM's path before its checks, as the real one does. A
key file holds one primary key per line, each optionally followed by ``rvk:``
and the fingerprint of its designated revoker, or ``sub:`` and the fingerprint
of a subkey. The stub `createrepo_c` writes a primary.xml that lists each
package's location, and the stub `gpg` writes the signing key into the
signature and lists a key file's keys in the real one's order, failing as it
does on an empty file. It imports a secret key from stdin into
`$GNUPGHOME/secret-keys`, which takes a key file's form, failing as the real
one does on input that holds no key, lists that file's keys the same way, and
fails when `$GNUPGHOME` is not a directory. The stub `gh`
serves the fake releases in `$FAKE_GH/releases.json`, in the order `gh release
list` gives them, and their assets under `$FAKE_GH/assets/TAG/`, logging each
call to `$FAKE_GH/calls`; it runs each `--jq` filter with jq, as gh does with
its built-in one. Each stub logs its arguments to `$KEY_SEEN` when it sees
`RPM_SIGNING_KEY` in its environment. ci.yml's dnf-repo job runs the real tools.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Literal

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "packaging" / "dnf-repo.sh"
SIGNER = "0123456789ABCDEF0123456789ABCDEF01234567"
OTHER = "89ABCDEF0123456789ABCDEF0123456789ABCDEF"
URL = "https://github.com/ORG/REPO/releases/download/"
USAGE = """\
dnf-repo.sh: usage: packaging/dnf-repo.sh sign FINGERPRINT KEYFILE RPM
       packaging/dnf-repo.sh metadata FINGERPRINT KEYFILE URL RPMDIR OUTDIR [PREVIOUS]
       packaging/dnf-repo.sh prune KEYFILE RPMDIR
       packaging/dnf-repo.sh fingerprint
       packaging/dnf-repo.sh release RPM KEYFILE OUTDIR
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
    sys.exit(1 if signer.endswith("damaged") else 0)
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
    if signer.endswith("damaged"):
        print("    Payload SHA256 digest: BAD")
    if signer.endswith("+bad"):
        print("    Header OpenPGP V4 RSA/SHA512 signature, key fingerprint: abc: BAD")
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
import os, pathlib, re, sys
args = sys.argv[1:]

def show(path, primary_type, sub_type):
    lines = [line.split() for line in open(path) if line.strip()]
    for primary, *extras in lines:
        print(f"{primary_type}:-:4096:1:0123456789ABCDEF:1700000000:::-:::scSC::::::23::0:")
        for extra in extras:
            if extra.startswith("rvk:"):
                print(f"rvk:::1::::::{extra[4:]}:80:")
        print(f"fpr:::::::::{primary}:")  # codespell:ignore fpr
        for extra in extras:
            if extra.startswith("sub:"):
                print(f"{sub_type}:-:4096:1:89ABCDEF01234567:1700000000::::::s::::::23:")
                print(f"fpr:::::::::{extra[4:]}:")  # codespell:ignore fpr
    return lines

if "--import" in args:
    keys = sys.stdin.read()
    if not re.search(r"^[0-9A-F]{40}\\b", keys, re.MULTILINE):
        print("gpg: no valid OpenPGP data found.", file=sys.stderr)
        sys.exit(2)
    with open(pathlib.Path(os.environ["GNUPGHOME"]) / "secret-keys", "a") as keyring:
        keyring.write(keys)
    sys.exit(0)
if "--show-keys" in args:
    if not show(args[-1], "pub", "sub"):
        sys.exit("gpg: no valid OpenPGP data found.")
    sys.exit(0)
if "--list-secret-keys" in args:
    home = pathlib.Path(os.environ["GNUPGHOME"])
    if not home.is_dir():
        sys.exit(f"gpg: {home} is not a directory")
    keyring = home / "secret-keys"
    if keyring.exists():
        show(keyring, "sec", "ssb")
    sys.exit(0)
signer = args[args.index("--local-user") + 1]
open(args[args.index("--output") + 1], "w").write(signer)
""",
    "gpgconf": """\
import sys
sys.exit(0 if sys.argv[1:] == ["--kill", "all"] else 1)
""",
    "gh": """\
import argparse, json, os, pathlib, shutil, subprocess, sys
fake = pathlib.Path(os.environ["FAKE_GH"])
with open(fake / "calls", "a") as calls:
    calls.write(" ".join(sys.argv[1:]).replace("\\n", " ") + "\\n")
parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument("group", choices=["release"])
parser.add_argument("command", choices=["list", "view", "download"])
parser.add_argument("tag", nargs="?")
parser.add_argument("--exclude-drafts", action="store_true")
parser.add_argument("--exclude-pre-releases", action="store_true")
parser.add_argument("--limit", type=int, default=30)
parser.add_argument("--json")
parser.add_argument("--jq")
parser.add_argument("--pattern")
parser.add_argument("--dir")
args = parser.parse_args()
releases = json.loads((fake / "releases.json").read_text())
if args.command == "download":
    asset = fake / "assets" / args.tag / args.pattern
    if not asset.is_file():
        sys.exit("no assets match the file pattern")
    pathlib.Path(args.dir).mkdir(parents=True, exist_ok=True)
    shutil.copy(asset, args.dir)
    sys.exit(0)
fields = args.json.split(",")
if args.command == "list":
    found = [
        r for r in releases
        if not (args.exclude_drafts and r["isDraft"])
        and not (args.exclude_pre_releases and r["isPrerelease"])
    ][: args.limit]
    data = [{f: r[f] for f in fields} for r in found]
else:
    found = [r for r in releases if (r["tagName"] == args.tag if args.tag else r["isLatest"])]
    if not found:
        sys.exit("release not found")
    data = {f: found[0][f] for f in fields}
sys.exit(subprocess.run(["jq", "-r", args.jq], input=json.dumps(data), text=True).returncode)
""",
}

# Run first by each stub.
KEY_SEEN = """\
import os, sys
if "RPM_SIGNING_KEY" in os.environ and "KEY_SEEN" in os.environ:
    with open(os.environ["KEY_SEEN"], "a") as seen:
        seen.write(" ".join([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + "\\n")
"""


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in STUBS.items():
        stub = bin_dir / name
        stub.write_text(f"#!{sys.executable}\n{KEY_SEEN}{text}", encoding="utf-8")
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
        pytest.param(["sign", SIGNER, "KEY"], id="sign without RPM"),
        pytest.param(["sign", SIGNER, "KEY", "a.rpm", "b.rpm"], id="sign with two RPMs"),
        pytest.param(["metadata", SIGNER, "KEY", URL, "rpms"], id="metadata without OUTDIR"),
        pytest.param(
            ["metadata", SIGNER, "KEY", URL, "rpms", "out", "prev", "x"], id="metadata, extra"
        ),
        pytest.param(["prune", "KEY"], id="prune without RPMDIR"),
        pytest.param(["prune", "KEY", "rpms", "x"], id="prune, extra"),
        pytest.param(["fingerprint", "x"], id="fingerprint, extra"),
        pytest.param(["release", "app.noarch.rpm", "KEY"], id="release without OUTDIR"),
        pytest.param(["release", "app.noarch.rpm", "KEY", "out", "x"], id="release, extra"),
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
    args = [keyfile, rpm] if mode == "sign" else [keyfile, URL, tmp_path / "rpms", tmp_path / "out"]
    result = run(env, mode, fingerprint, *args)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: not a key fingerprint (40 hex digits): {fingerprint}\n"


def test_sign_signs_the_rpm_in_place_with_the_key(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    rpm = add_rpm(tmp_path, "v1.0.0rc1", "1.0.0~rc1", "-")
    result = run(env, "sign", SIGNER, keyfile, rpm)
    assert result.returncode == 0, result.stderr
    assert rpm.read_text(encoding="utf-8") == f"app 1.0.0~rc1 {SIGNER}"


@pytest.mark.parametrize("missing", ["keyfile", "rpm"])
def test_sign_fails_on_a_missing_input(
    env: dict[str, str], tmp_path: Path, keyfile: Path, missing: str
) -> None:
    rpm = add_rpm(tmp_path, "v1.0.0", "1.0.0", "-")
    path = tmp_path / "missing"
    if missing == "keyfile":
        result = run(env, "sign", SIGNER, path, rpm)
        error = f"no such key file: {path}"
    else:
        result = run(env, "sign", SIGNER, keyfile, path)
        error = f"no such RPM: {path}"
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {error}\n"
    assert rpm.read_text(encoding="utf-8") == "app 1.0.0 -"


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


def test_metadata_fails_on_an_rpm_signed_by_another_key(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", OTHER)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {rpm} is signed by a key not in the key file\n"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("signer", ["bad", f"{SIGNER}-damaged", f"{OTHER}-damaged", f"{OTHER}+bad"])
def test_metadata_fails_on_a_bad_signature_or_a_damaged_signed_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path, signer: str
) -> None:
    add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", SIGNER)
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", signer)
    result = metadata(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr.startswith(f"dnf-repo.sh: {rpm} has a bad signature, or is damaged:\n")
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


def sign_or_metadata(
    env: dict[str, str], tmp_path: Path, keyfile: Path, mode: str, rpm: Path
) -> subprocess.CompletedProcess[str]:
    if mode == "sign":
        return run(env, "sign", SIGNER, keyfile, rpm)
    return metadata(env, tmp_path, keyfile)


@pytest.mark.parametrize("mode", ["sign", "metadata"])
@pytest.mark.parametrize(
    "keys",
    [
        pytest.param(f"{OTHER}\n", id="another key"),
        pytest.param(f"{OTHER} rvk:{SIGNER}\n", id="another key the signing key may revoke"),
        pytest.param(f"{OTHER} sub:{SIGNER}\n", id="the signing key as another key's subkey"),
    ],
)
def test_the_key_file_must_hold_the_signing_key_as_a_primary_key(
    env: dict[str, str], tmp_path: Path, keyfile: Path, mode: str, keys: str
) -> None:
    keyfile.write_text(keys, encoding="utf-8")
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", OTHER)
    result = sign_or_metadata(env, tmp_path, keyfile, mode, rpm)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {keyfile} doesn't hold the key {SIGNER}\n"
    assert rpm.read_text(encoding="utf-8") == f"app 1.1.0 {OTHER}"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("mode", ["sign", "metadata"])
def test_a_key_file_gpg_cant_read_fails_with_gpgs_error(
    env: dict[str, str], tmp_path: Path, keyfile: Path, mode: str
) -> None:
    keyfile.write_text("", encoding="utf-8")
    rpm = add_rpm(tmp_path / "rpms", "v1.1.0", "1.1.0", "-")
    result = sign_or_metadata(env, tmp_path, keyfile, mode, rpm)
    assert result.returncode == 1
    assert result.stderr == (
        f"dnf-repo.sh: can't read the keys in {keyfile}: gpg: no valid OpenPGP data found.\n"
    )
    assert rpm.read_text(encoding="utf-8") == "app 1.1.0 -"
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


def test_prune_deletes_only_rpms_signed_by_another_key(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    rpmdir = tmp_path / "rpms"
    kept = [
        add_rpm(rpmdir, "v1.0.0", "1.0.0", "-"),
        add_rpm(rpmdir, "v1.1.0", "1.1.0", "-4"),
        add_rpm(rpmdir, "v1.3.0", "1.3.0", SIGNER),
    ]
    other = add_rpm(rpmdir, "v1.2.0", "1.2.0", OTHER)
    result = run(env, "prune", keyfile, rpmdir)
    assert result.returncode == 0, result.stderr
    assert result.stderr == (
        f"dnf-repo.sh: warning: leaving out {other}: it is signed by a key not in {keyfile}\n"
    )
    assert not other.exists()
    assert all(rpm.exists() for rpm in kept)


@pytest.mark.parametrize(
    ("signer", "error"),
    [
        pytest.param("damaged", "is damaged", id="damaged, unsigned"),
        pytest.param(
            f"{OTHER}-damaged", "has a bad signature, or is damaged", id="damaged, other key"
        ),
        pytest.param("bad", "has a bad signature, or is damaged", id="bad signature"),
        pytest.param(
            f"{OTHER}+bad",
            "has a bad signature, or is damaged",
            id="bad signature beside another key's",
        ),
    ],
)
def test_prune_fails_on_a_damaged_rpm_or_a_bad_signature(
    env: dict[str, str], tmp_path: Path, keyfile: Path, signer: str, error: str
) -> None:
    rpm = add_rpm(tmp_path / "rpms", "v1.0.0", "1.0.0", signer)
    result = run(env, "prune", keyfile, tmp_path / "rpms")
    assert result.returncode == 1
    assert result.stderr.startswith(f"dnf-repo.sh: {rpm} {error}:\n")
    assert rpm.exists()


@pytest.mark.parametrize("missing", ["keyfile", "rpmdir"])
def test_prune_fails_on_a_missing_input(
    env: dict[str, str], tmp_path: Path, keyfile: Path, missing: str
) -> None:
    rpmdir = tmp_path / "rpms"
    rpmdir.mkdir()
    path = tmp_path / "missing"
    if missing == "keyfile":
        result = run(env, "prune", path, rpmdir)
        error = f"no such key file: {path}"
    else:
        result = run(env, "prune", keyfile, path)
        error = f"no such directory: {path}"
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {error}\n"


@pytest.mark.parametrize(
    "keys",
    [
        pytest.param(f"{SIGNER}\n", id="one key"),
        pytest.param(f"{SIGNER} sub:{OTHER}\n", id="one key with a subkey"),
        pytest.param(f"{SIGNER} rvk:{OTHER}\n", id="one key with a designated revoker"),
    ],
)
def test_fingerprint_prints_the_one_secret_keys_fingerprint(
    env: dict[str, str], tmp_path: Path, keys: str
) -> None:
    (tmp_path / "secret-keys").write_text(keys, encoding="utf-8")
    result = run({**env, "GNUPGHOME": str(tmp_path)}, "fingerprint")
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{SIGNER}\n"


@pytest.mark.parametrize(
    "keys", [pytest.param(None, id="no key"), pytest.param(f"{SIGNER}\n{OTHER}\n", id="two keys")]
)
def test_fingerprint_fails_unless_the_keyring_holds_one_secret_key(
    env: dict[str, str], tmp_path: Path, keys: str | None
) -> None:
    if keys is not None:
        (tmp_path / "secret-keys").write_text(keys, encoding="utf-8")
    result = run({**env, "GNUPGHOME": str(tmp_path)}, "fingerprint")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "dnf-repo.sh: the keyring must hold one secret key\n"


def test_fingerprint_fails_with_gpgs_error_when_gpg_cant_list_the_keys(
    env: dict[str, str], tmp_path: Path
) -> None:
    home = tmp_path / "gnupg"
    home.write_text("", encoding="utf-8")
    result = run({**env, "GNUPGHOME": str(home)}, "fingerprint")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        f"dnf-repo.sh: can't list the secret keys: gpg: {home} is not a directory\n"
    )


TAG = "v0.0.7"
NO_KEY_ERROR = (
    "::error::The rpm-signing environment has no RPM_SIGNING_KEY secret. Make the key as"
    " docs/signing-key.md says, or delete packaging/dnf.repo to release the RPM unsigned, with no"
    " dnf repository.\n"
)


def version_of(tag: str) -> str:
    return tag.removeprefix("v").replace("-", "~")


class Releases:
    """The stub `gh`'s releases, each published after every one added before it."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.releases: list[dict[str, object]] = []
        (root / "assets").mkdir(parents=True)
        self.save()

    def save(self) -> None:
        (self.root / "releases.json").write_text(json.dumps(self.releases), encoding="utf-8")

    def add(
        self,
        tag: str,
        signer: str | None = SIGNER,
        *,
        bundle: Path | None = None,
        kind: Literal["full", "latest", "pre-release", "draft"] = "full",
        older_commit: bool = False,
    ) -> None:
        # signer None: no RPM. older_commit: gh lists the release last.
        assets = self.root / "assets" / tag
        if signer is None:
            assets.mkdir()
        else:
            add_rpm(self.root / "assets", tag, version_of(tag), signer)
        if bundle is not None:
            shutil.copy(bundle, assets / "app-dnf-repo.tar.gz")
        release: dict[str, object] = {
            "tagName": tag,
            "isDraft": kind == "draft",
            "isPrerelease": kind == "pre-release",
            "isLatest": kind == "latest",
            "publishedAt": f"2026-01-01T00:{len(self.releases):02d}:00Z",
            "assets": [{"name": path.name} for path in sorted(assets.iterdir())],
        }
        if older_commit:
            self.releases.append(release)
        else:
            self.releases.insert(0, release)
        self.save()


@pytest.fixture
def releases(tmp_path: Path) -> Releases:
    return Releases(tmp_path / "fake")


def gh_calls(tmp_path: Path) -> list[str]:
    path = tmp_path / "fake" / "calls"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def downloaded_rpms(tmp_path: Path) -> list[str]:
    return [
        call.split()[2]
        for call in gh_calls(tmp_path)
        if call.startswith("release download") and "--pattern app.noarch.rpm " in call
    ]


def release_env(
    env: dict[str, str], tmp_path: Path, tag: str, **changes: str | None
) -> dict[str, str]:
    if shutil.which("jq") is None:
        pytest.fail("the release tests need jq: the stub gh runs each --jq filter with it")
    (tmp_path / "tmp").mkdir()
    result = {
        **env,
        "RPM_SIGNING_KEY": f"{SIGNER}\n",
        "PRERELEASE": "false",
        "KEEP": "4",
        "GITHUB_REF_NAME": tag,
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "ORG/REPO",
        "GH_REPO": "ORG/REPO",
        "GH_TOKEN": "token",
        "FAKE_GH": str(tmp_path / "fake"),
        "KEY_SEEN": str(tmp_path / "key-seen"),
        "TMPDIR": str(tmp_path / "tmp"),
    }
    # Unset, as in the job, so the stub gpg fails unless release sets its own.
    result.pop("GNUPGHOME", None)
    for name, value in changes.items():
        if value is None:
            result.pop(name, None)
        else:
            result[name] = value
    return result


def release(
    env: dict[str, str], tmp_path: Path, keyfile: Path, tag: str = TAG, **changes: str | None
) -> subprocess.CompletedProcess[str]:
    rpm = add_rpm(tmp_path / "job", tag, version_of(tag), "-")
    result = run(
        release_env(env, tmp_path, tag, **changes), "release", rpm, keyfile, tmp_path / "out"
    )
    # Passing or failing, the run removes its keyring and scratch directories.
    assert not any((tmp_path / "tmp").iterdir())
    return result


def key_seen(tmp_path: Path) -> list[str]:
    path = tmp_path / "key-seen"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def job_rpm(tmp_path: Path, tag: str = TAG) -> str:
    return (tmp_path / "job" / tag / "app.noarch.rpm").read_text(encoding="utf-8")


def out_rpm(tmp_path: Path) -> str:
    return (tmp_path / "out" / "app.noarch.rpm").read_text(encoding="utf-8")


def out_files(tmp_path: Path) -> list[str]:
    return sorted(path.name for path in (tmp_path / "out").iterdir())


def indexed(tmp_path: Path) -> str:
    return bundle_files(tmp_path / "out" / "app-dnf-repo.tar.gz")["repodata/new-primary.xml"]


def urls(*tags: str) -> str:
    return "\n".join(f"{URL}{tag}/app.noarch.rpm" for tag in tags)


def previous_bundle(tmp_path: Path) -> Path:
    return write_bundle(
        tmp_path / "previous.tar.gz",
        {
            "repodata/repomd.xml": '<location href="repodata/old-primary.xml"/>\n',
            "repodata/old-primary.xml": "old primary",
        },
    )


@pytest.mark.parametrize("secret", [pytest.param("", id="empty"), pytest.param(None, id="unset")])
@pytest.mark.usefixtures("releases")
def test_release_fails_without_the_secret(
    env: dict[str, str], tmp_path: Path, keyfile: Path, secret: str | None
) -> None:
    result = release(env, tmp_path, keyfile, RPM_SIGNING_KEY=secret)
    assert result.returncode == 1
    assert result.stdout == NO_KEY_ERROR
    assert gh_calls(tmp_path) == []
    assert job_rpm(tmp_path) == "app 0.0.7 -"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("prerelease", ["", "yes", None])
@pytest.mark.usefixtures("releases")
def test_release_fails_unless_the_notes_job_says_whether_it_is_a_pre_release(
    env: dict[str, str], tmp_path: Path, keyfile: Path, prerelease: str | None
) -> None:
    result = release(env, tmp_path, keyfile, PRERELEASE=prerelease)
    assert result.returncode == 1
    assert result.stdout == "::error::The notes job did not say whether this is a pre-release\n"
    assert gh_calls(tmp_path) == []
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        pytest.param({"KEEP": None}, "KEEP is not set", id="no KEEP"),
        pytest.param({"KEEP": "four"}, "KEEP is not a number: four", id="KEEP not a number"),
        pytest.param({"GITHUB_REF_NAME": ""}, "GITHUB_REF_NAME is not set", id="no tag"),
    ],
)
@pytest.mark.usefixtures("releases")
def test_release_needs_its_settings(
    env: dict[str, str],
    tmp_path: Path,
    keyfile: Path,
    changes: dict[str, str | None],
    error: str,
) -> None:
    result = release(env, tmp_path, keyfile, TAG, **changes)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {error}\n"
    assert gh_calls(tmp_path) == []
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("name", ["missing.noarch.rpm", "app.rpm"])
def test_release_needs_an_rpm_named_for_its_package(
    env: dict[str, str], tmp_path: Path, keyfile: Path, name: str
) -> None:
    rpm = tmp_path / name
    error = "no such RPM" if name.startswith("missing") else "not named NAME.noarch.rpm"
    if name == "app.rpm":
        rpm.write_text("app 0.0.7 -", encoding="utf-8")
    result = run(release_env(env, tmp_path, TAG), "release", rpm, keyfile, tmp_path / "out")
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {error}: {rpm}\n"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    ("secret", "error"),
    [
        pytest.param(
            f"{SIGNER}\n{OTHER}\n", "dnf-repo.sh: the keyring must hold one secret key", id="two"
        ),
        pytest.param("garbage", "gpg: no valid OpenPGP data found.", id="none"),
    ],
)
@pytest.mark.usefixtures("releases")
def test_release_fails_unless_the_secret_holds_one_key(
    env: dict[str, str], tmp_path: Path, keyfile: Path, secret: str, error: str
) -> None:
    keyfile.write_text(f"{SIGNER}\n{OTHER}\n", encoding="utf-8")
    result = release(env, tmp_path, keyfile, RPM_SIGNING_KEY=secret)
    assert result.returncode == 1
    assert result.stdout == "::error::RPM_SIGNING_KEY must hold one secret key\n"
    assert result.stderr == f"{error}\n"
    assert gh_calls(tmp_path) == []
    assert job_rpm(tmp_path) == "app 0.0.7 -"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    ("tag", "prerelease"), [pytest.param(TAG, "false"), pytest.param("v0.0.7-rc.1", "true")]
)
@pytest.mark.usefixtures("releases")
def test_release_fails_unless_the_key_file_holds_the_key(
    env: dict[str, str],
    tmp_path: Path,
    keyfile: Path,
    tag: str,
    prerelease: str,
) -> None:
    keyfile.write_text(f"{OTHER}\n", encoding="utf-8")
    result = release(env, tmp_path, keyfile, tag, PRERELEASE=prerelease)
    assert result.returncode == 1
    assert result.stderr == f"dnf-repo.sh: {keyfile} doesn't hold the key {SIGNER}\n"
    assert gh_calls(tmp_path) == []
    assert job_rpm(tmp_path, tag) == f"app {version_of(tag)} -"
    assert not (tmp_path / "out").exists()


@pytest.mark.usefixtures("releases")
def test_release_fails_on_a_key_file_gpg_cant_read(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    keyfile.write_text("", encoding="utf-8")
    result = release(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert result.stderr.startswith(f"dnf-repo.sh: can't read the keys in {keyfile}: ")
    assert gh_calls(tmp_path) == []
    assert not (tmp_path / "out").exists()


def test_a_pre_release_gets_the_signed_rpm_only(
    env: dict[str, str], tmp_path: Path, keyfile: Path, releases: Releases
) -> None:
    releases.add("v0.0.6", kind="latest")
    result = release(env, tmp_path, keyfile, "v0.0.7-rc.1", PRERELEASE="true")
    assert result.returncode == 0, result.stderr
    assert out_files(tmp_path) == ["app.noarch.rpm"]
    assert out_rpm(tmp_path) == f"app 0.0.7~rc.1 {SIGNER}"
    assert gh_calls(tmp_path) == []
    # Not even the import's gpg: a real one starts a gpg-agent that keeps its environment.
    assert key_seen(tmp_path) == []


@pytest.mark.usefixtures("releases")
def test_a_first_full_release_bundles_its_own_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path
) -> None:
    result = release(env, tmp_path, keyfile, "v0.0.6")
    bundle = tmp_path / "out" / "app-dnf-repo.tar.gz"
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{bundle}\n"
    assert out_files(tmp_path) == ["app-dnf-repo.tar.gz", "app.noarch.rpm"]
    assert out_rpm(tmp_path) == f"app 0.0.6 {SIGNER}"
    assert [call.split()[:2] for call in gh_calls(tmp_path)] == [["release", "list"]]
    files = bundle_files(bundle)
    assert files["repodata/new-primary.xml"] == urls("v0.0.6")
    assert files["repodata/repomd.xml.asc"] == SIGNER
    assert files["RPM-GPG-KEY-app"] == f"{SIGNER}\n"
    assert key_seen(tmp_path) == []


@pytest.mark.parametrize("other_key_in_key_file", [False, True])
def test_a_full_release_bundles_the_full_releases_published_most_recently(
    env: dict[str, str],
    tmp_path: Path,
    keyfile: Path,
    releases: Releases,
    other_key_in_key_file: bool,
) -> None:
    releases.add("v0.0.1")
    releases.add("v0.0.2")
    releases.add("v0.0.3", None)
    releases.add("v0.0.4", OTHER)
    releases.add("v0.0.5")
    releases.add("v0.0.6", bundle=previous_bundle(tmp_path), kind="latest")
    releases.add("v0.0.7-rc.1", kind="pre-release")
    releases.add("v0.0.9", kind="draft")
    if other_key_in_key_file:
        keyfile.write_text(f"{SIGNER}\n{OTHER}\n", encoding="utf-8")
    result = release(env, tmp_path, keyfile)
    assert result.returncode == 0, result.stderr
    assert downloaded_rpms(tmp_path) == ["v0.0.6", "v0.0.5", "v0.0.4"]
    assert "release view v0.0.3 --json assets --jq any(.assets[]; .name == env.ASSET)" in (
        gh_calls(tmp_path)
    )
    assert any(
        call.startswith("release download v0.0.6 --pattern app-dnf-repo.tar.gz --dir ")
        for call in gh_calls(tmp_path)
    )
    files = bundle_files(tmp_path / "out" / "app-dnf-repo.tar.gz")
    assert files["repodata/old-primary.xml"] == "old primary"
    assert key_seen(tmp_path) == []
    if other_key_in_key_file:
        assert result.stderr == ""
        assert indexed(tmp_path) == urls("v0.0.4", "v0.0.5", "v0.0.6", "v0.0.7")
    else:
        assert re.fullmatch(
            r"dnf-repo.sh: warning: leaving out \S+/releases/v0\.0\.4/app\.noarch\.rpm:"
            rf" it is signed by a key not in {re.escape(str(keyfile))}\n",
            result.stderr,
        )
        assert indexed(tmp_path) == urls("v0.0.5", "v0.0.6", "v0.0.7")


def test_a_release_on_an_older_commit_counts_from_when_it_was_published(
    env: dict[str, str], tmp_path: Path, keyfile: Path, releases: Releases
) -> None:
    for tag in ["v0.0.1", "v0.0.2", "v0.0.4", "v0.0.5"]:
        releases.add(tag)
    releases.add("v0.0.6", bundle=previous_bundle(tmp_path), kind="latest")
    releases.add("v0.0.3", older_commit=True)
    result = release(env, tmp_path, keyfile)
    assert result.returncode == 0, result.stderr
    assert downloaded_rpms(tmp_path) == ["v0.0.3", "v0.0.6", "v0.0.5", "v0.0.4"]
    assert indexed(tmp_path) == urls("v0.0.3", "v0.0.4", "v0.0.5", "v0.0.6", "v0.0.7")


def test_a_re_run_does_not_download_its_own_release(
    env: dict[str, str], tmp_path: Path, keyfile: Path, releases: Releases
) -> None:
    releases.add("v0.0.5")
    releases.add("v0.0.6", bundle=previous_bundle(tmp_path), kind="latest")
    result = release(env, tmp_path, keyfile, "v0.0.6")
    assert result.returncode == 0, result.stderr
    assert downloaded_rpms(tmp_path) == ["v0.0.5"]
    assert indexed(tmp_path) == urls("v0.0.5", "v0.0.6")


def test_a_full_release_leaves_out_an_unsigned_earlier_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path, releases: Releases
) -> None:
    releases.add("v0.0.5", "-")
    releases.add("v0.0.6", bundle=previous_bundle(tmp_path), kind="latest")
    result = release(env, tmp_path, keyfile)
    assert result.returncode == 0, result.stderr
    assert re.fullmatch(
        r"dnf-repo.sh: warning: leaving out \S+/releases/v0\.0\.5/app\.noarch\.rpm:"
        r" it is not signed\n",
        result.stderr,
    )
    assert indexed(tmp_path) == urls("v0.0.6", "v0.0.7")


@pytest.mark.parametrize("signer", [f"{SIGNER}-damaged", f"{OTHER}-damaged"])
def test_a_full_release_fails_on_a_damaged_earlier_rpm(
    env: dict[str, str], tmp_path: Path, keyfile: Path, releases: Releases, signer: str
) -> None:
    releases.add("v0.0.5", signer)
    releases.add("v0.0.6", bundle=previous_bundle(tmp_path), kind="latest")
    result = release(env, tmp_path, keyfile)
    assert result.returncode == 1
    assert re.search(
        r"^dnf-repo.sh: \S+/releases/v0\.0\.5/app\.noarch\.rpm has a bad signature, or is damaged:$",
        result.stderr,
        re.MULTILINE,
    )
    assert out_files(tmp_path) == ["app.noarch.rpm"]
