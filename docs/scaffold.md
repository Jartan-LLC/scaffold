# Scaffold

This project started from [scaffold](https://github.com/Jartan-LLC/scaffold), a GitHub
template repository, or is scaffold itself. This page covers the parts that came from
scaffold and how to pull in later scaffold changes.

## Liza

The `liza` Feature activates Liza in each clone when the container is created, and
`liza-toolchain` adds its agent tools. To undo activation in a clone, run `liza-deactivate`;
the next container create activates it again. To opt out of either Feature, follow the
Removal steps on its page ([liza](https://github.com/Jartan-LLC/enchantments/blob/main/src/liza/README.md),
[liza-toolchain](https://github.com/Jartan-LLC/enchantments/blob/main/src/liza-toolchain/README.md)).

Each Claude session selects its mode at start; start a new session to switch.

| Mode | For | Start it |
|---|---|---|
| Pairing | everyday work; you approve each step | open Claude in an activated clone |
| Adversarial Pairing | one high-stakes change, reviewed by separate sessions | see below |
| Multi-agent | a goal large enough to decompose and run unattended | see below |

**Adversarial Pairing.** Open one Claude session per role and keep the pairing's
blackboard and worktree in `.adversarial/`, because a multi-agent init deletes `.liza/` and `.worktrees/`:

```text
/adversarial-pairing doer .adversarial/<name>.md
/adversarial-pairing reviewer-1 .adversarial/<name>.md
```

When the doer asks where to create its worktree, answer `.adversarial/worktrees/<name>`.
In that worktree, the doer runs `uv venv` and `make install` before its first `make check`,
so the checks run against the worktree's own code rather than the main checkout's install.

**Multi-agent.** Commit a goal document first, then:

```bash
liza init "<goal>" --spec specs/<goal>.md --post-worktree-cmd "uv venv -q --allow-existing && make install"
liza tui
```

`--post-worktree-cmd` gives each task worktree its own `.venv`, which every `make` target
there uses, and runs `make install` in it. That install skips the git hook: Liza sets the
worktree's `core.hooksPath`, and `pre-commit install` refuses to run with it set. Fill in
`GUARDRAILS.md` before a first run. Liza's
[Getting Started](https://github.com/liza-mas/liza/blob/main/GETTING_STARTED.md) covers
the rest of the run: checkpoints, the operator session, logs.

## CI

`ci.yml`'s `check` job passes when every job in its `needs` list passed or was skipped. A
job joins or leaves that gate through two entries in `check`, `needs` and the `results`
array, so a job you write or uncomment goes in both. A step added to an existing job, such as
a Node check in `lint`, needs no `check` change.

The `python` job runs pyright, builds and checks the package, and runs pip-audit, which is
advisory: its failure doesn't fail the job, and adds a warning annotation naming pip-audit
to the `python` check.

The `changes` job skips `python` and `test` when every changed file is Markdown,
`.pre-commit-config.yaml`, or under `docs/`, `.claude/` or `.github/`. A change to
`README.md`, `.github/workflows/ci.yml`, `.github/workflows/release.yml` or anything under
`src/` or `tests/` always runs them. If a Python job or a test comes to read a file in a
skipped path, such as a local action under `.github/actions/`, add it to `_PYTHON_READS` in
`ci/changes.py`. `tests/ci/test_changes.py` fails when a test names such a file as
`Path(__file__).resolve().parents[N] / "..."` and `_PYTHON_READS` lacks it. A path built any
other way escapes that check.

The `rpm` job runs on every change while `packaging/rpm.spec` exists: it builds the RPM,
running the spec's `%check`, and installs it in Fedora. While `packaging/dnf.repo` also exists,
the `dnf-repo` job builds a test dnf repository with `packaging/dnf-repo.sh` and checks in
Fedora that `dnf` installs and upgrades from it and refuses unsigned packages and tampered
metadata; `ci/dnf-repo-test.sh` lists its checks.

The `docker` job builds the image `publish-docker.yml` pushes, for the runner's platform
only, when a change touches one of its build inputs, which `_DOCKER_INPUTS` in
`ci/changes.py` lists: the `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml` and the
files the `Dockerfile` copies by name. If the `Dockerfile` comes to copy another file by
name, add it there; `tests/ci/test_changes.py` fails when the list misses a source of an
uppercase `COPY`, on one line or continued with a backslash. An `ADD`, or a `COPY` written
any other way, escapes that check. The job doesn't run the image: uncomment its smoke-test
step once the `Dockerfile` has a start command.

The dev container job runs only when a change touches one of its build inputs, which
`_DEVCONTAINER_INPUTS` in `ci/changes.py` lists. `pyproject.toml`, `package.json` and pnpm's
lockfile and config are not among them; `ci/requirements.txt` is, because `post-create.sh`
reads uv's pin from it. Scheduled and manual runs run every job, so a `pyproject.toml` or
Node manifest change that breaks only the dev container build shows at the weekly run, not
on its PR. A push to `main` that skips the Python jobs doesn't check the dev extras, which
resolve at run time; the weekly run or the next PR that runs those jobs does.

A private repository pays for Actions minutes, and GitHub bills each job as at least one
minute. Two levers cut those minutes:

- Each Dependabot PR runs CI. In each `updates` entry of `.github/dependabot.yml` whose
  PRs should batch a month of updates instead of a week, set `interval: "monthly"` and
  remove `day: "monday"`, which applies to weekly schedules.
- CI doesn't run on a pushed branch other than `main` until it has a PR, and each push to
  a PR cancels the run before it, which still bills the minutes it used. A review needs no
  PR, so finish review rounds on the pushed branch before opening the PR.

## Publishing

A `v*` tag runs these workflows, and `pages.yml` also runs on each push to `main`:

| Workflow | Publishes |
|---|---|
| `release.yml` | a GitHub Release whose notes are the tag's `CHANGELOG.md` section (`## [1.2.0]` for `v1.2.0`) with its hard-wrapped lines joined, or GitHub's generated notes, with a warning in the run, when there is no `CHANGELOG.md` or that section is missing, empty or holds only HTML comments. A PEP 440 or SemVer pre-release tag (`v1.2.0rc1`, `v1.2.0-rc.1`) makes a pre-release. A full release becomes Latest only when no full release has a higher version. Runs go one at a time, in push order: a tag's run waits until the previous tag's run finishes |
| `rpm.yml`, run by `release.yml` | while `packaging/rpm.spec` exists, `NAME.noarch.rpm` on the GitHub Release, built from the tag and installed in Fedora first, with a build provenance attestation in a public repository. A failed build creates no Release. A tag gets the RPM in one of these forms: `vX.Y.Z`; `vX.Y.ZaN`, `vX.Y.ZbN` or `vX.Y.ZrcN`; or `vX.Y.Z-` and a SemVer pre-release of lowercase letters, digits and dots that starts with a letter (`v1.2.0-rc.1`), unless PEP 440 reads it as a post-release or development release (`v1.2.0-post.1`, `v1.2.0-dev3`). Any other tag gets no Release, while the other workflows here still run |
| `release.yml`'s `sign` job | while `packaging/dnf.repo` exists, the RPM signed with the key in the `rpm-signing` environment and, on a full release, `NAME-dnf-repo.tar.gz` on the GitHub Release: the dnf repository's signed metadata, indexing that release's RPM and those of the earlier full releases published most recently, by date rather than version, up to `KEEP` in the job. A failed or rejected `sign` job creates no Release |
| `pages.yml`, once renamed from `pages.yml.example`, after each `release.yml` run that succeeds, and each push to `main` | the GitHub Pages site: the Sphinx docs while `docs/conf.py` exists and, while `packaging/dnf.repo` exists, the dnf repository under `rpm/`, unpacked from the Latest release's `NAME-dnf-repo.tar.gz`. Its `verify` job then installs the package from the Latest release and fails unless the live repository, its signature checked, lists that release as the newest version. The docs build installs only releases at least a week old. A failed docs build deploys nothing, `rpm/` included. Until a release has the bundle the site has no `rpm/`; after that, a Latest release without one fails the run |
| `publish-pypi.yml` | the package to PyPI from the `pypi` environment, once the tag matches `pyproject.toml`'s `version`, through [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no token secret is stored. The build installs only the hash-pinned packages in `ci/build-requirements.txt` |
| `publish-docker.yml` | multi-arch images to `ghcr.io/OWNER/REPO` from the `ghcr` environment, with the built-in `GITHUB_TOKEN`, no secret needed. The build installs the hash-pinned packages in `ci/build-requirements.txt`, and runtime dependencies only from releases at least a week old. Images are tagged with the tag's version and, unless it is a pre-release, `X.Y`; `latest` moves only when the tag is the highest release. A tag that is no PEP 440 or SemVer version, or makes no valid Docker tag, fails the run before the build |

## Syncing template updates

In a project created with *Use this template*, `.scaffold-sync` holds the newest scaffold
commit it has ported or skipped. List the scaffold commits after it:

```bash
git remote add upstream https://github.com/Jartan-LLC/scaffold.git  # once per clone; the clone onboarding ran in has it
git fetch upstream
git log --oneline --reverse "$(cat .scaffold-sync)"..upstream/main  # not yet dealt with, oldest first
```

Oldest first, port each commit you want, and skip the others by leaving them out:

```bash
git cherry-pick -n <sha>   # stages the commit's change without committing it
```

- `cherry-pick` merges three ways, across the unrelated history *Use this template* creates.
  Resolve each conflict before the next pick, then adapt the change to this project. Where
  scaffold's side of a conflict holds a `TODO(/onboard)` marker or a placeholder, keep this
  project's side.
- A file this project deleted comes up as a `modify/delete` conflict. `git rm <path>` keeps it
  deleted, and the rest of the commit applies.
- Pick one commit at a time. A range (`A..B`) stops at its first conflict and won't continue
  over the staged result.
- `-n` makes no commit, so scaffold's subjects, and the `(#NNN)` numbers in them, which name
  scaffold's issues, stay out of this project's history.
- Scaffold's `main` is linear, so every commit picks without `-m`.

Then record the newest commit you ported or skipped, and commit `.scaffold-sync` with the
port, so the file always matches what the repository contains:

```bash
git rev-parse <sha> > .scaffold-sync
```

Open a PR, so CI runs before the changes land.
