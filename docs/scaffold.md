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
`README.md`, `.github/workflows/ci.yml` or anything under `src/` or `tests/` always runs
them. If a Python job comes to use a file in a skipped path, such as a local action under
`.github/actions/`, add it to `_PYTHON_READS` in `ci/changes.py`.

The `rpm` job runs on every change while `packaging/rpm.spec` exists: it builds the RPM,
running the spec's `%check`, and installs it in Fedora.

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

Nothing publishes until you push a `v*` tag. Each tag runs these workflows:

| Workflow | Publishes |
|---|---|
| `release.yml` | a GitHub Release whose notes are the tag's `CHANGELOG.md` section (`## [1.2.0]` for `v1.2.0`) with its hard-wrapped lines joined, or GitHub's generated notes, with a warning in the run, when there is no `CHANGELOG.md` or that section is missing, empty or holds only HTML comments. A PEP 440 or SemVer pre-release tag (`v1.2.0rc1`, `v1.2.0-rc.1`) makes a pre-release |
| `rpm.yml`, run by `release.yml` | while `packaging/rpm.spec` exists, `NAME.noarch.rpm` on the GitHub Release, built from the tag and installed in Fedora first, with a build provenance attestation in a public repository. A failed build creates no Release. `rpm.sh` takes `vX.Y.Z`, `vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`, and `vX.Y.Z-` followed by a SemVer pre-release of letters, digits and dots that starts with a letter (`v1.2.0-rc.1`) and that PEP 440 doesn't read as a post-release or development release (`v1.2.0-post.1`, `v1.2.0-dev3`). Any other tag gets no Release, while the other workflows here still publish |
| `publish-pypi.yml` | the package to PyPI from the `pypi` environment, through [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no token secret is stored |
| `publish-docker.yml` | multi-arch images to `ghcr.io/OWNER/REPO` from the `ghcr` environment, with the built-in `GITHUB_TOKEN`, no secret needed. Images are tagged `X.Y.Z` and `X.Y`; `latest` moves only when the tag is the highest release |

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
