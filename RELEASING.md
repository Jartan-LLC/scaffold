# Releasing

How to cut a release from `main`. The workflows a tag runs are listed in
[Publishing](docs/scaffold.md#publishing).

## Cut a release

1. Choose the version, written `X.Y.Z` below, a pre-release suffix included. Write a
   pre-release as `1.2.0-rc.1` (or `-alpha.1`, `-beta.1`), not `1.2.0rc1`:
   `publish-docker.yml` tags images only from SemVer versions. [Pre-releases](#pre-releases)
   says what one publishes.
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

The tag starts `release.yml`, `publish-pypi.yml` and `publish-docker.yml`.

1. Approve the `publish-pypi.yml` and `publish-docker.yml` runs: open each from
   `gh run list --branch vX.Y.Z` and choose Review deployments. A run waits for this only when
   its environment (`pypi`, `ghcr`) has required reviewers.
2. Check that every run succeeded:

   ```bash
   gh run list --branch vX.Y.Z
   ```

3. Check the notes with `gh release view vX.Y.Z`. If the `release.yml` run warns that it used
   generated notes, `CHANGELOG.md` had nothing under `## [X.Y.Z]` at the tag; the warning says
   why.

## Pre-releases

For a tag with a pre-release version, such as `v1.2.0-rc.1`:

- `release.yml` creates a GitHub pre-release, which GitHub never marks Latest;
- `publish-pypi.yml` publishes a PyPI pre-release, with the version normalized (`1.2.0rc1`);
- `publish-docker.yml` tags the image `1.2.0-rc.1` only, leaving `1.2` and `latest` where
  they were.
