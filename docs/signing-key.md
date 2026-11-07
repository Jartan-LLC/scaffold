# Signing key

How to make, rotate and replace the key that signs the RPMs and the dnf repository.
`RELEASING.md` covers the releases it signs.

While `packaging/dnf.repo` exists, `release.yml`'s `sign` job signs each RPM, and each full
release's dnf repository metadata, with the key in the `RPM_SIGNING_KEY` secret of the
`rpm-signing` environment. The package installs `packaging/RPM-GPG-KEY`, and dnf trusts only
the keys in it, so the job refuses to sign with a key that file doesn't hold. Without the
secret, the job fails and the tag gets no GitHub Release. A re-run checks out the same tagged
commit, so it fails again while that commit's `packaging/RPM-GPG-KEY` doesn't hold the secret's
key.

<!-- TODO(/onboard): in this page's commands, replace ORG/REPO with the GitHub org and repo, NAME with Name in packaging/rpm.spec, and ADDRESS with the key's contact email address. -->

## Making a key

Make the first key before the first release, once the `rpm-signing` environment exists.

1. On a trusted machine, not in CI, make an RSA-4096 key with no expiry and no passphrase, in a
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
2. Store the secret key in the environment, and write the public key for the package:

   ```bash
   gpg --armor --export-secret-keys FINGERPRINT | gh secret set RPM_SIGNING_KEY --env rpm-signing
   gpg --armor --export FINGERPRINT >packaging/RPM-GPG-KEY
   ```

   Commit `packaging/RPM-GPG-KEY` through a pull request.
3. Copy `$GNUPGHOME` to encrypted offline storage, then delete it here
   (`gpgconf --kill gpg-agent; rm -rf "$GNUPGHOME"`). It holds the secret key, and the
   revocation certificate gpg wrote to `openpgp-revocs.d/FINGERPRINT.rev`, which
   [If the key leaks](#if-the-key-leaks) needs.
4. Write the key's fingerprint in place of `FINGERPRINT`, or of the leaked key's after a leak,
   in `RELEASING.md`'s Installing the RPM section and in your README's copy of it, so users can
   check the key the package installs. Delete the onboarding marker above that paragraph in
   `RELEASING.md`, if it is still there.

## Rotating the key

dnf trusts a new key only once a package the user installed has brought it, so a rotation takes
two releases at least:

1. Make the new key as step 1 of [Making a key](#making-a-key) says, with NEW_FINGERPRINT its
   fingerprint. Add its public key to `packaging/RPM-GPG-KEY` after the old one, then store it
   offline as step 3 says:

   ```bash
   gpg --armor --export NEW_FINGERPRINT >>packaging/RPM-GPG-KEY
   ```

   Commit the file through a pull request, and release as usual: the old key still signs.
2. At least 3 months and 2 releases later, switch the secret to the new key, from its offline
   copy, and write the new fingerprint in place of the old one in `RELEASING.md`'s Installing
   the RPM section and your README:

   ```text
   GNUPGHOME=<the new key's copy> gpg --armor --export-secret-keys NEW_FINGERPRINT |
     gh secret set RPM_SIGNING_KEY --env rpm-signing
   ```

A user who installs none of the releases in between stops getting updates, with only a warning in
dnf's output, until they install from the release URL again, as `RELEASING.md`'s Installing the RPM
section says. Leave the old key in `packaging/RPM-GPG-KEY` until the new key has signed every
release in the dnf repository, which holds the latest full release and the earlier full releases
published most recently, by date rather than version, as many as `KEEP` in `release.yml`'s `sign`
job says: the job leaves an earlier release out of the repository once the file no longer holds the
key that signed it.

## If the key leaks

1. Revoke the key, LEAKED_FINGERPRINT below, in a copy of its offline `$GNUPGHOME`, and export
   the revoked certificate.
   gpg writes the revocation certificate with a `:` before its first line, so that importing it
   takes this deliberate step:

   ```text
   export GNUPGHOME=<a copy of the leaked key's directory>
   sed 's/^:-----/-----/' "$GNUPGHOME/openpgp-revocs.d/LEAKED_FINGERPRINT.rev" | gpg --import
   gpg --armor --export LEAKED_FINGERPRINT >RPM-GPG-KEY-NAME-revoked
   ```

2. Make a new key as [Making a key](#making-a-key) says. Its step 2 replaces the leaked key in
   `packaging/RPM-GPG-KEY` with it.
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
