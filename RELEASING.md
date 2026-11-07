# Releasing

How to cut a release from `main`. The workflows a tag runs are listed in
[Publishing](docs/scaffold.md#publishing).

## Cut a release

1. Choose the version, written `X.Y.Z` below, a pre-release suffix included. Write a
   pre-release as `1.2.0-rc.1`. [Pre-releases](#pre-releases) says what one publishes.
2. On a branch from `main`, move the entries under `## [Unreleased]` in `CHANGELOG.md` to a new
   section below it, headed `## [X.Y.Z] - YYYY-MM-DD`. That section becomes the release notes;
   an entry may wrap across lines, since the notes join them. Then replace the `[Unreleased]`
   link, which before the first release points at `commits/main`, and add a link for the new
   version. Keep all link definitions at the end of the file, below every section and after a
   blank line, since one written straight after an entry becomes part of that entry's text:

   <!-- TODO(/onboard): replace ORG/REPO in the links below with the GitHub org and repo. -->

   ```markdown
   [Unreleased]: https://github.com/ORG/REPO/compare/vX.Y.Z...HEAD
   [X.Y.Z]: https://github.com/ORG/REPO/releases/tag/vX.Y.Z
   ```

3. On the same branch, set `version = "X.Y.Z"` in `pyproject.toml`, written exactly as the tag
   writes it. The built package takes its version from there. `publish-pypi.yml` fails without
   publishing when that version differs from the tag, `1.2.0rc1` against `v1.2.0-rc.1`
   included, while the other workflows the tag starts publish regardless.
   <!-- TODO(/onboard): if the project isn't Python, name the file that holds its version, or delete this step. -->
4. Open a pull request from that branch and merge it once its checks pass.
5. Wait for CI to pass on the commit the merge made on `main`. A `v*` tag publishes without
   waiting for CI, so tag only a commit whose CI run passed:

   ```bash
   sha=$(gh pr view <PR number> --json mergeCommit --jq .mergeCommit.oid)
   gh run list --workflow ci.yml --commit "$sha"
   gh run watch <run ID> --exit-status   # exits non-zero if the run failed
   ```

   `gh run list` prints nothing until GitHub has created the run; run it again until the run
   appears. If the run fails, fix `main` through another pull request and repeat this step
   with that one.
6. Tag that commit and push the tag:

   ```bash
   git fetch origin   # so the merge commit exists locally
   sha=$(gh pr view <PR number> --json mergeCommit --jq .mergeCommit.oid)   # again, in case the CI step's shell is gone
   git tag vX.Y.Z "$sha"
   git push origin vX.Y.Z
   ```

   The tag is `v` and the version exactly as the changelog heading writes it: the release and
   publish workflows run on `v*` tags, and `release.yml` takes the notes from `## [X.Y.Z]`.

## After the tag

The tag starts `release.yml`, `publish-pypi.yml` and `publish-docker.yml`. While
`packaging/rpm.spec` exists, a failed RPM build or attestation leaves the tag without a GitHub
Release; if the failure was transient, such as a mirror timeout, `gh run rerun <run ID> --failed`
on the `release.yml` run creates it. While `packaging/dnf.repo` exists, a failed or rejected
`sign` job also leaves the tag without a GitHub Release, and [Signing key](docs/signing-key.md)
says when a re-run fails again.

1. Approve the `publish-pypi.yml` and `publish-docker.yml` runs: open each from
   `gh run list --branch vX.Y.Z` and choose Review deployments. A run waits for this only when
   its environment (`pypi`, `ghcr`) has required reviewers. While `packaging/dnf.repo` exists,
   approve the `release.yml` run's `sign` job the same way, in the `rpm-signing` environment.
2. Check that every run succeeded:

   ```bash
   gh run list --branch vX.Y.Z
   ```

3. Check the notes with `gh release view vX.Y.Z`. If the `release.yml` run warns that it used
   generated notes, `CHANGELOG.md` had nothing under `## [X.Y.Z]` at the tag; the warning says
   why. While `packaging/rpm.spec` exists, check that it lists `NAME.noarch.rpm` too, where
   `NAME` is `Name` in `packaging/rpm.spec`. While `packaging/dnf.repo` exists, a full release
   lists `NAME-dnf-repo.tar.gz` as well, the dnf repository's signed metadata; it leaves out an
   earlier release whose `release.yml` run hadn't created its GitHub Release when this run's
   `sign` job listed the releases, and the next full release's bundle has it again.

## Pre-releases

For a tag with a pre-release version, such as `v1.2.0-rc.1`:

- `release.yml` creates a GitHub pre-release, which GitHub never marks Latest;
- `publish-pypi.yml` publishes a PyPI pre-release, with the version normalized (`1.2.0rc1`);
- while `packaging/rpm.spec` exists, the RPM's version is `1.2.0~rc.1`, which `dnf` upgrades in
  place to `1.2.0`;
- while `packaging/dnf.repo` exists, the RPM is signed, but stays out of the dnf repository,
  which would otherwise upgrade every user to it;
- `publish-docker.yml` tags the image `1.2.0-rc.1` only, leaving `1.2` and `latest` where they
  were.

## Installing the RPM

<!-- TODO(/onboard): in the commands below, replace ORG/REPO with the GitHub org and repo, and NAME with Name in packaging/rpm.spec. -->

Users install the RPM, and later upgrade it in place, with:

```bash
sudo dnf install https://github.com/ORG/REPO/releases/latest/download/NAME.noarch.rpm
```

`dnf` checks no signature on a package installed from a URL, so it prints `Warning: skipped
OpenPGP checks for 1 package`. In a public repository, to check that a release built it,
download it and verify its attestation before installing it:

```bash
gh release download --repo ORG/REPO --pattern NAME.noarch.rpm
gh attestation verify NAME.noarch.rpm --repo ORG/REPO
sudo dnf install ./NAME.noarch.rpm
```

<!-- TODO(/onboard): while packaging/dnf.repo exists, replace FINGERPRINT below with the signing key's fingerprint once you make it, as step 4 of docs/signing-key.md's Making a key says. -->

While `packaging/dnf.repo` exists, the key that signs the RPMs and the dnf repository has the
fingerprint `FINGERPRINT`; `gpg --show-keys /etc/pki/rpm-gpg/RPM-GPG-KEY-NAME` prints the
fingerprints of the keys the package installed.
