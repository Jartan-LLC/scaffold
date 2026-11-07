# Releasing

How to cut a release from `main`. What each publishing target needs before its first release
is in [Publishing](docs/scaffold.md#publishing).

## Cut a release

1. Choose the version, written `X.Y.Z` below. Write a pre-release as `X.Y.Z-rc.N` (or
   `-alpha.N`, `-beta.N`), not `X.Y.ZrcN`: `publish-docker.yml` tags images only from SemVer
   versions. [Pre-releases](#pre-releases) says what one publishes.
2. On a branch from `main`, move the entries under `## [Unreleased]` in `CHANGELOG.md` to a new
   section below it, headed `## [X.Y.Z] - YYYY-MM-DD`. That section becomes the release notes;
   an entry may wrap across lines, since the notes join them. Then update the links at the end
   of the file:

   ```markdown
   [Unreleased]: https://github.com/OWNER/REPO/compare/vX.Y.Z...HEAD
   [X.Y.Z]: https://github.com/OWNER/REPO/releases/tag/vX.Y.Z
   ```

3. On the same branch, set `version = "X.Y.Z"` in `pyproject.toml`. PyPI gets this version,
   whatever the tag says.
   <!-- TODO(/onboard): if the project isn't Python, name the file that holds its version, or delete this step. -->
4. Open a pull request with both changes and merge it once its checks pass.
5. Wait for CI to pass on the commit the merge made on `main`. A `v*` tag publishes without
   waiting for CI, so tag only a commit whose CI run passed:

   ```bash
   sha=$(gh pr view <PR number> --json mergeCommit --jq .mergeCommit.oid)
   gh run list --workflow ci.yml --commit "$sha"
   gh run watch <run ID> --exit-status   # exits non-zero if the run failed
   ```

   If it fails, fix `main` through another pull request and repeat this step with that one.
6. Tag that commit and push the tag:

   ```bash
   git fetch origin
   git tag vX.Y.Z "$sha"
   git push origin vX.Y.Z
   ```

   The tag is `v` and the version exactly as the changelog heading writes it: the release and
   publish workflows run on `v*` tags, and `release.yml` takes the notes from `## [X.Y.Z]`.

## After the tag

The tag starts `release.yml`, which creates the GitHub Release, and `publish-pypi.yml` and
`publish-docker.yml` where the repository has them.

1. Approve each publish run waiting on its `pypi` or `ghcr` environment: open the run from
   `gh run list --branch vX.Y.Z` and choose Review deployments. A run waits only when its
   environment has required reviewers.
2. Check that every run succeeded:

   ```bash
   gh run list --branch vX.Y.Z
   ```

3. Check the notes with `gh release view vX.Y.Z`. If the `release.yml` run warns that it used
   generated notes, `CHANGELOG.md` had nothing under `## [X.Y.Z]` at the tag; the warning says
   why.

## Pre-releases

A tag with a pre-release version, such as `vX.Y.Z-rc.N`:

- creates a GitHub pre-release, which GitHub never marks Latest;
- publishes a PyPI pre-release, with the version normalized (`1.2.0rc1` for `1.2.0-rc.1`);
- tags the image `X.Y.Z-rc.N` only, leaving `X.Y` and `latest` where they were.
