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

   While `packaging/dnf.repo` exists, a full release's dnf repository bundle leaves out an
   earlier release whose `release.yml` run hadn't created its GitHub Release when this run's
   `sign` job listed the releases; the next full release's bundle has it again.

## After the tag

The tag starts `release.yml`, `publish-pypi.yml` and `publish-docker.yml`. While
`packaging/rpm.spec` exists, a failed RPM build or attestation leaves the tag without a GitHub
Release; if the failure was transient, such as a mirror timeout, `gh run rerun <run ID> --failed`
on the `release.yml` run creates it. While `packaging/dnf.repo` exists, a failed or rejected
`sign` job also leaves the tag without a GitHub Release, and [Signing key](#signing-key) says
when a re-run fails again.

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
   lists `NAME-dnf-repo.tar.gz` as well, the dnf repository's signed metadata.

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

While `packaging/dnf.repo` exists, the key that signs the RPMs and the dnf repository has the
fingerprint `FINGERPRINT`; `gpg --show-keys /etc/pki/rpm-gpg/RPM-GPG-KEY-NAME` prints the
fingerprints of the keys the package installed.

## Signing key

While `packaging/dnf.repo` exists, `release.yml`'s `sign` job signs each RPM, and each full
release's dnf repository metadata, with the key in the `RPM_SIGNING_KEY` secret of the
`rpm-signing` environment. The package installs `packaging/RPM-GPG-KEY`, and dnf trusts only
the keys in it, so the job refuses to sign with a key that file doesn't hold. Without the
secret, the job fails and the tag gets no GitHub Release. A re-run checks out the same tagged
commit, so it fails again while that commit's `packaging/RPM-GPG-KEY` doesn't hold the secret's
key.

<!-- TODO(/onboard): in this section's commands, replace ORG/REPO with the GitHub org and repo, NAME with Name in packaging/rpm.spec, and ADDRESS with the key's contact email address. -->

### Setting up the key

Before the first release:

1. Create the `rpm-signing` environment, open to `v*` tags only:

   ```bash
   gh api -X PUT repos/{owner}/{repo}/environments/rpm-signing \
     -F 'deployment_branch_policy[protected_branches]=false' \
     -F 'deployment_branch_policy[custom_branch_policies]=true'
   gh api -X POST repos/{owner}/{repo}/environments/rpm-signing/deployment-branch-policies \
     -f name='v*' -f type=tag
   ```

   Then add required reviewers to it (Settings > Environments), so no tag gets the key without
   a reviewer's approval. On GitHub Free, Pro and Team, required reviewers need a public
   repository, which the dnf repository needs anyway.
2. On a trusted machine, not in CI, make an RSA-4096 key with no expiry and no passphrase, in a
   keyring of its own:

   ```bash
   export GNUPGHOME=$(mktemp -d)
   gpg --batch --passphrase '' --quick-gen-key 'NAME release signing <ADDRESS>' rsa4096 sign never
   gpg --list-secret-keys   # the 40-character line is the key's fingerprint, FINGERPRINT below
   ```

   - RSA-4096 works on every Fedora and EL client; an Ed25519 key fails on EL 8.
   - dnf never learns that a key was revoked, so an expiry adds no safety, and an expired key
     stops every user's updates.
   - A passphrase would be a second secret in the same environment, behind the same approval.
3. Store the secret key in the environment, and write the public key for the package:

   ```bash
   gpg --armor --export-secret-keys FINGERPRINT | gh secret set RPM_SIGNING_KEY --env rpm-signing
   gpg --armor --export FINGERPRINT >packaging/RPM-GPG-KEY
   ```

   Commit `packaging/RPM-GPG-KEY` through a pull request.
4. Copy `$GNUPGHOME` to encrypted offline storage, then delete it here
   (`gpgconf --kill gpg-agent; rm -rf "$GNUPGHOME"`). It holds the secret key, and the
   revocation certificate gpg wrote to `openpgp-revocs.d/FINGERPRINT.rev`, which
   [If the key leaks](#if-the-key-leaks) needs.
5. Write the key's fingerprint in place of `FINGERPRINT`, or of the leaked key's after a leak,
   in [Installing the RPM](#installing-the-rpm) and in your README's copy of that section, so
   users can check the key the package installs.

### Rotating the key

dnf trusts a new key only once a package the user installed has brought it, so a rotation takes
two releases at least:

1. Make the new key as step 2 of [Setting up the key](#setting-up-the-key) says, with
   NEW_FINGERPRINT its fingerprint. Add its public key to `packaging/RPM-GPG-KEY` after the old
   one, then store it offline as step 4 says:

   ```bash
   gpg --armor --export NEW_FINGERPRINT >>packaging/RPM-GPG-KEY
   ```

   Commit the file through a pull request, and release as usual: the old key still signs.
2. At least 3 months and 2 releases later, switch the secret to the new key, from its offline
   copy, and write the new fingerprint in place of the old one in
   [Installing the RPM](#installing-the-rpm) and your README:

   ```bash
   GNUPGHOME=<the new key's copy> gpg --armor --export-secret-keys NEW_FINGERPRINT |
     gh secret set RPM_SIGNING_KEY --env rpm-signing
   ```

A user who installs none of the releases in between stops getting updates, with only a warning
in dnf's output, until they install from the release URL again, as
[Installing the RPM](#installing-the-rpm) says. Leave the old key in `packaging/RPM-GPG-KEY`
until the new key has signed every release in the dnf repository, which holds the latest full
release and the earlier full releases created most recently, by date rather than version, as many
as `KEEP` in `release.yml`'s `sign` job says: the job leaves an earlier release out of the
repository once the file no longer holds the key that signed it.

### If the key leaks

1. Revoke the key, LEAKED_FINGERPRINT below, in a copy of its offline `$GNUPGHOME`, and export
   the revoked certificate.
   gpg writes the revocation certificate with a `:` before its first line, so that importing it
   takes this deliberate step:

   ```bash
   export GNUPGHOME=<a copy of the leaked key's directory>
   sed 's/^:-----/-----/' "$GNUPGHOME/openpgp-revocs.d/LEAKED_FINGERPRINT.rev" | gpg --import
   gpg --armor --export LEAKED_FINGERPRINT >RPM-GPG-KEY-NAME-revoked
   ```

2. Make a new key as [Setting up the key](#setting-up-the-key) says, from step 2. Step 3
   replaces the leaked key in `packaging/RPM-GPG-KEY` with it.
3. Release. The releases the leaked key signed leave the dnf repository, and keep their RPMs.
4. Attach the revoked certificate to that release, and announce the leak with the new
   fingerprint:

   ```bash
   gh release upload vX.Y.Z RPM-GPG-KEY-NAME-revoked
   ```

dnf never fetches again a key it already has, so each user must stop trusting the leaked key,
then install from the release URL to get the new one:

```bash
curl -LO https://github.com/ORG/REPO/releases/download/vX.Y.Z/RPM-GPG-KEY-NAME-revoked
sudo rpmkeys --import RPM-GPG-KEY-NAME-revoked
sudo dnf install https://github.com/ORG/REPO/releases/latest/download/NAME.noarch.rpm
```
