# Setting up the template

Work through the sections below in order, from Decide to Finish. `/onboard` in Claude Code
works through the page for you. [What's included](#whats-included), after Finish, lists what
the template ships. Finish deletes this page; [`scaffold.md`](scaffold.md) covers what stays
useful afterwards.

## Decide

Settle these first: the procedures and markers below take their values from the answers.
An item whose answer needs neither, such as which workflows to keep, says what to do with it.

- [ ] Project name and one-line description; for Python, the distribution and import names,
      and whether it has a command-line interface
- [ ] GitHub org and repo, and the code owners
- [ ] Stack: language and framework, deployment target, and, if it isn't Python, its
      lint, fix, typecheck, test, docs and build commands
- [ ] License, and the author and copyright holder ([License](#license))
- [ ] Contacts for conduct reports and security reports, one address or two. Both are
      published, so give addresses you are willing to publish
- [ ] Which enchantments Features to keep ([Features](#features))
- [ ] Publishing targets: the PyPI package, the container image, the docs site, an RPM for
      Fedora, with or without a dnf repository (with one, also the public key that signs it)
      ([details](#publishing-targets))
- [ ] Whether to keep `Dockerfile` (its marker says what goes with it, and the
      `publish-docker.yml` row in [Publishing](scaffold.md#publishing) and the sentences
      naming it in `RELEASING.md` go too),
      `.github/workflows/scorecard.yml` (an OpenSSF score; it skips on private repos) and
      `.github/workflows/external-link-check.yml` (a weekly check for broken external links).
      Delete each workflow you don't keep
- [ ] Optionally: version corrections for `AGENTS.md`, and the supported versions and
      response targets for `.github/SECURITY.md`

### Publishing targets

Keep `release.yml` whatever you publish: it creates a GitHub Release for each `v*` tag, in any
stack. If you keep the RPM, a tag in a form the `rpm.yml` row in
[Publishing](scaffold.md#publishing) doesn't list gets no GitHub Release.

- PyPI package: keep `publish-pypi.yml`, and set up its environment in
  [GitHub settings](#publishing-environments). If the package's version isn't
  `[project] version` in `pyproject.toml`, repoint `ver=` in the workflow's tag check, and
  name where it is in `RELEASING.md`'s version step and the `publish-pypi.yml` row in
  [Publishing](scaffold.md#publishing).
- Container image: keep `publish-docker.yml`, set up its environment in
  [GitHub settings](#publishing-environments), and give the `Dockerfile` a real entrypoint.
- Docs site: for a single version, use GitHub Pages: set Settings > Pages > Source to "GitHub
  Actions", then rename `.github/workflows/pages.yml.example` to `pages.yml`. For a version
  per release, use Read the Docs: rename `.readthedocs.yaml.example` to `.readthedocs.yaml`
  and import the repo there.
- RPM for Fedora, attached to each GitHub Release: for files that run unchanged on every
  Fedora release, such as a shell script, keep `packaging/`, and copy `RELEASING.md`'s
  Installing the RPM section into your README. In the README's copy, delete the
  `TODO(/onboard)` marker above the fingerprint paragraph, and "While `packaging/dnf.repo`
  exists, " from the start of that paragraph; without a dnf repository, delete that paragraph
  too. For a Python package, publish to PyPI instead.
  A dnf repository lets users get new releases with `dnf upgrade`; a private repository can't
  publish one, because dnf can't fetch its Release assets.

For the PyPI package or the container image, if you drop it, delete its publish workflow and
its row in [Publishing](scaffold.md#publishing), and delete or rewrite each sentence in
`RELEASING.md` that names that workflow. To drop the RPM, delete `packaging/`,
`tests/packaging/`, `ci/dnf-repo-test.sh`, `ci/dnf_repo_server.py`, `docs/signing-key.md` and
its entry in `docs/index.md`, the `docker` entry for `/packaging` in `.github/dependabot.yml`,
the `rpm.yml` and `sign` rows in Publishing, and, in `RELEASING.md`, the Installing the RPM
section and each sentence and list item that opens with "while `packaging/rpm.spec` exists" or
"while `packaging/dnf.repo` exists". Keep `.github/workflows/rpm.yml` and the RPM jobs in
`ci.yml` and `release.yml`: they skip while the spec is missing.

To keep the RPM without the dnf repository, as a private repository must, delete
`packaging/dnf.repo`, `packaging/RPM-GPG-KEY`, `packaging/dnf-repo.sh`,
`tests/packaging/test_dnf_repo_sh.py`, `ci/dnf-repo-test.sh`, `ci/dnf_repo_server.py`,
`docs/signing-key.md` and its entry in `docs/index.md`, the spec's lines that make, install and
list those two files, with their comments, the `sign` row in Publishing, and, in `RELEASING.md`,
each sentence and list item that opens with "while `packaging/dnf.repo` exists". Keep the `sign`
job in `release.yml`: it skips while `packaging/dnf.repo` is missing.

## Procedures

Run these in order. Each runs on the files the one before it left.

1. [ ] [Features](#features)
2. [ ] [Rename the Python package](#python-package), or [tear down Python](#not-a-python-project)
3. [ ] [Stack](#stack)
4. [ ] [License](#license)
5. [ ] Tests (Python): add tests of your code. `tests/test_smoke.py` only checks that the
       CLI stub runs. Replace it, unless the project has no CLI: then the `__main__.py`
       marker deletes it

### Features

For each [enchantments](https://github.com/Jartan-LLC/enchantments) Feature you decline:

1. While it is still declared, run the in-clone steps of the Removal section on its page, if
   it has one ([the Features list](https://github.com/Jartan-LLC/enchantments#features) links
   each page).
2. Remove its entry from `devcontainer.json` and its key from `devcontainer-lock.json`.
3. Do the rest of its Removal steps in their order, such as removing the container and then a
   volume, and rebuild.

Also:

- Declining `claude-code` means declining `codebase-memory-mcp` too, if you added it, and
  declining `liza` means declining `liza-toolchain`.
- Declining `liza` also means deleting the [Liza](scaffold.md#liza) section of
  `docs/scaffold.md`; declining only `liza-toolchain`, removing it from that section's first
  paragraph.
- To keep a code graph without `liza-toolchain`, declare `codebase-memory-mcp` in its place.
- A Feature in your VS Code `dev.containers.defaultFeatures` comes back on rebuild, so
  declining it here applies only to contributors who don't set it. Declare `liza` and
  `liza-toolchain` both in `devcontainer.json` or both only in `defaultFeatures`
  ([liza-toolchain](https://github.com/Jartan-LLC/enchantments/blob/main/src/liza-toolchain/README.md)).

### Python package

Rename the `app` stub to your import name:

1. `pyproject.toml`: set `name` and `description`, and point
   `[tool.hatch.build.targets.wheel]` `packages` at the new directory. Without it the
   build fails.
2. Rename `src/app/`.
3. Update the imports: `from app.log import …` in `src/app/__main__.py` and
   `tests/test_log.py`, `from app.__main__ import …` in `tests/test_smoke.py`.
4. Update the `python -m app` references: `prog=` and the module docstring in `__main__.py`
   (or replace that stub), and the `Dockerfile` `CMD` hint. Also update `--cov=app` in
   `ci.yml`'s commented `integration-tests` job.
5. Resolve the markers in `docs/getting-started.md` and `docs/reference.md`. The strict docs
   build fails while `reference.md` names `app`.

### Not a Python project

This deletes the docs site, and with it some markers, so it runs before [Markers](#markers).
Keep `docs/scaffold.md` and `docs/signing-key.md`, which read fine on GitHub without Sphinx,
and this page, which Finish deletes.

Keep `ci/`. `ci.yml`'s `changes` job runs `ci/changes.py`, `release.yml` runs
`ci/release_notes.py` and `publish-docker.yml` runs `ci/versions.py`, all on the runner's
`python3`. This repository doesn't test, lint or type-check those scripts: scaffold does,
and its changes to them come in by [syncing](scaffold.md#syncing-template-updates), so leave
them as they are. `ci/changes.py` still describes the `python` and `test` jobs and prints a
`python` output that nothing reads.

1. Move `[tool.codespell]` from `pyproject.toml` to a `.codespellrc`.
2. Delete `pyproject.toml`, `src/`, `tests/`, everything in `docs/` but `scaffold.md`,
   `signing-key.md` and this page, `.readthedocs.yaml.example`,
   `.github/workflows/pages.yml.example`, `.github/workflows/publish-pypi.yml` and
   `.github/workflows/dependency-audit.yml`. If not containerized, also `Dockerfile`,
   `.dockerignore`, `.github/workflows/publish-docker.yml` and the commented `docker` job in
   `.github/workflows/ci.yml`.
3. In `.pre-commit-config.yaml`, remove the `ruff-pre-commit` entry. Keep the other hooks.
4. In `.github/workflows/ci.yml`, remove the `python`, `test` and `docs` jobs and their
   `check` entries (`docs/scaffold.md`, CI), and the commented `integration-tests` job. In
   the `changes` job, remove the `python:` line under `outputs`. `lint` stays.
5. Keep the `Makefile`: it is the verify entry point in every stack. Point its `lint`, `fix`,
   `typecheck`, `test` and `docs` targets at your stack's commands, and replace the Python
   lines in `check` (`uv build`, `twine check`, `pip-audit`), so `make check` stays the one
   verify gate.
6. In `ci/requirements.txt`, delete the `twine` and `pip-audit` entries with their comment
   lines, and make the `uv` comment "installer, resolver and venv manager". In the header,
   end the sentence on the tools' own dependencies at "Their own dependencies are neither
   pinned nor hashed.", and replace the sentence on where the other tools' versions live
   with "The lint tools are versioned by their hook revs in .pre-commit-config.yaml."
7. In `.github/dependabot.yml`, delete the `pip` entry for `/` and keep the one for `/ci`. In
   the `/ci` entry's comment, delete the sentence "Separate from the "/" entry above so a
   CI-tool bump lands as its own reviewable PR rather than riding along with a project
   dependency."
8. In `CONTRIBUTING.md`, rewrite the `make install` setup and the "Requires Python 3.12+ and
   uv" line for your stack.
9. Trim the Python parts of `docs/scaffold.md`. In its [Publishing](scaffold.md#publishing)
   table, delete the `publish-pypi.yml` row and, if not containerized, the
   `publish-docker.yml` row.
10. In `RELEASING.md`, delete or rewrite each sentence that names `publish-pypi.yml` and,
    if not containerized, `publish-docker.yml`.

### Stack

- `devcontainer.json`: add or remove Features and extensions for your stack.
- `post-start.sh`: add commands to run on each container start. The Docker socket fix and
  Codespaces environment overrides are already there.
- The `Makefile`'s `install` target: add your stack's install (for example
  `go mod download`). It runs on a bare host and from `post-create.sh`.
- `.gitignore` and `.editorconfig`: add your stack's patterns and rules.
- `.github/workflows/ci.yml`: prune it to your stack. [CI](scaffold.md#ci) says how a job
  leaves the `check` gate.
- `.github/dependabot.yml`: remove the ecosystems you don't use, add the ones you need, and
  adjust `directory` where manifests aren't at the root. Keep the `pip` entry for `/ci`: it
  updates `ci/requirements.txt`.

### License

Keep `LICENSE` (MIT) with your own year and name, or replace it with one of the `LICENSE.*`
templates, filling in `[year]` and `[fullname]`: `LICENSE.proprietary` is all rights
reserved, for private or closed-source work. A license not among the templates replaces
`LICENSE` the same way. Then delete the `LICENSE.*` files.

## Markers

Every line the template ships is true both in the template and in a project made from it,
carries a `TODO(/onboard): <what to do>` marker, is changed by a procedure above, or sits in
a file onboarding deletes or replaces (this page, `.claude/commands/onboard.md`, `README.md`
and the license files). Text that waits on project code, such as the `ci.yml` jobs to
uncomment once you add their inputs, carries no marker: it stays true after onboarding.
In a project that isn't Python, `ci/changes.py` keeps its lines on the Python jobs
([Not a Python project](#not-a-python-project)).

1. List the markers:

   ```bash
   git grep -n 'TODO(/onboard)'
   ```

2. Do what each marker says, then delete the marker. Never fill in a value nobody gave.
   Decide gives every value the markers need but the optional ones. With no version
   corrections, resolving the `AGENTS.md` marker deletes its examples. With no supported
   versions or response targets, rewrite each of those marked lines in `.github/SECURITY.md`
   to state only the default it gives (for the supported versions, `Report against the
   latest release.`), and delete the comment with the example table.
3. Run the grep again. It should print only this page, the marker on its `docs/index.md`
   entry, which Finish deletes, `.scaffold-sync`, which the next section fills or, in a
   fork, deletes, and, if you kept the dnf repository, the markers in `packaging/RPM-GPG-KEY`
   and `RELEASING.md`, which [Making a key](signing-key.md#making-a-key) resolves.

## Record the sync point

`.scaffold-sync` records the scaffold commit this repository has caught up to, so you can
pull in later template changes ([Syncing template updates](scaffold.md#syncing-template-updates)).
It ships holding a marker, because a file can't name the commit that contains it.

If you created the repository with *Use this template*, its first commit is an exact copy of
one scaffold commit's tree. Write that commit to the file:

```bash
git remote add upstream https://github.com/Jartan-LLC/scaffold.git
git fetch upstream
tree=$(git rev-parse "$(git rev-list --max-parents=0 HEAD)^{tree}")
sha=$(git log --format='%H %T' upstream/main | awk -v t="$tree" '$2 == t {print $1; exit}')
test -n "$sha" && echo "$sha" > .scaffold-sync
```

If `test -n` fails, the file keeps its marker:

- In a shallow clone (`git rev-parse --is-shallow-repository` prints `true`), run
  `git fetch --unshallow`, then run the block again from the `tree=` line.
- Otherwise, or if it fails again, no scaffold commit has the first commit's tree: write the
  scaffold commit you started from into the file by hand.

The `upstream` remote stays for [syncing](scaffold.md#syncing-template-updates).

If you forked scaffold instead, the history is shared, so later scaffold changes come in by a
merge. Delete `.scaffold-sync`, and rewrite
[Syncing template updates](scaffold.md#syncing-template-updates) as this merge in place of its
cherry-pick steps. The block is that section's new content, not a step to run now:

```bash
git remote add upstream https://github.com/Jartan-LLC/scaffold.git  # once per clone
git fetch upstream
git checkout -b template-update
git merge upstream/main   # resolve conflicts, keeping your customizations
```

## GitHub settings

- [ ] Private vulnerability reporting (Settings > Security): until it is on, the advisory
      form `SECURITY.md` links to does not exist
- [ ] The `major`/`minor`/`patch` labels Dependabot adds to its PRs ([details](#dependabot-labels))
- [ ] A branch ruleset for `main`: require PR reviews, require the `check` status to pass,
      block force pushes
- [ ] CodeQL default setup (Settings > Security > Code scanning)
- [ ] Secret scanning with push protection (Settings > Security > Secret Protection)
- [ ] Auto-merge (Settings > General > Allow auto-merge): Dependabot minor and patch PRs
      merge after CI passes
- [ ] Discussions (Settings > General > Features): the issue template config links to it
- [ ] For each publishing target you kept, its `pypi` or `ghcr` environment
      ([details](#publishing-environments))
- [ ] If you kept the dnf repository, its `rpm-signing` environment and the `RPM_SIGNING_KEY`
      secret ([details](#publishing-environments))

### Dependabot labels

Dependabot creates its own `dependencies` and ecosystem labels, but adds `major`, `minor` or
`patch` to its PRs only if those labels exist. Create them:

```bash
gh label create major --color B60205 --description "Major version update" --force
gh label create minor --color FBCA04 --description "Minor version update" --force
gh label create patch --color 0E8A16 --description "Patch version update" --force
```

### Publishing environments

`publish-pypi.yml` runs in the `pypi` environment and `publish-docker.yml` in `ghcr`. Create
the environment of each workflow you kept:

```bash
gh api -X PUT repos/{owner}/{repo}/environments/pypi
gh api -X PUT repos/{owner}/{repo}/environments/ghcr
```

In a public repository, add required reviewers to each (Settings > Environments), so each
publish waits for a reviewer's approval; a private repository needs GitHub Enterprise for
them. For `pypi`, also configure
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) for the environment, so no
token secret is stored. Until it is configured, `publish-pypi.yml` fails on every tag. Creating
`pypi` also clears the GitHub Actions VS Code extension's "environment `pypi` is not valid"
warning.

If you kept the dnf repository, `release.yml`'s `sign` job runs in `rpm-signing`, which holds
the signing key. Create it, open to `v*` tags only:

```bash
gh api -X PUT repos/{owner}/{repo}/environments/rpm-signing \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api -X POST repos/{owner}/{repo}/environments/rpm-signing/deployment-branch-policies \
  -f name='v*' -f type=tag
```

Then add required reviewers to it (Settings > Environments), so no tag gets the key without a
reviewer's approval. On GitHub Free, Pro and Team, required reviewers need a public repository,
which the dnf repository needs anyway. Make the first key as
[Making a key](signing-key.md#making-a-key) says.

## Finish

1. [ ] Replace `README.md` with your own, carrying over its badges adjusted for your repo
       ([details](#readme-badges)).
2. [ ] Delete this page, its entry in `docs/index.md` with the marker above it (unless
       tearing down Python deleted `docs/index.md`), and `.claude/commands/onboard.md`.
3. [ ] Run `git grep -n 'TODO(/onboard)'`. It must print nothing, or, until you make the
       signing key, only the markers in `packaging/RPM-GPG-KEY` and `RELEASING.md`.
4. [ ] Run `make check`.

### README badges

Copy the badge lines from the top of the template README into yours, then:

- Replace `Jartan-LLC/scaffold` with your org and repo in each badge.
- License badge: replace `MIT` in `license-MIT-blue` with your license. shields.io splits the
  badge text on `-`, so write each `-` in the name as `--` (`license-Apache--2.0-blue`).
- Delete the OpenSSF Scorecard badge if you deleted `scorecard.yml` or the repo is private.

## What's included

| Area | Contents |
|------|----------|
| `.devcontainer/` | Reproducible dev environment — Python 3.12, Node.js LTS, Docker, GitHub CLI, and the [enchantments](https://github.com/Jartan-LLC/enchantments) Features: Claude Code, the GitHub CLI login, Liza and its agent toolchain ([Features](#features) drops one). `post-create.sh` runs `make install`, which installs the project's dependencies into the system Python, as CI does: `containerEnv` sets `UV_SYSTEM_PYTHON`, so the container has no project `.venv`. It also installs the ruff version in the ruff hook's `# frozen:` comment, so the ruff extension formats on save as `make lint` does |
| `.claude/` | Claude Code project files — the `/onboard` command, which onboarding deletes, and `workspace/`, where agents keep plans and other working files, git-ignored |
| `.github/` | CI pipeline (active lint incl. workflow security lint via actionlint/zizmor, + Python typecheck/test/build + advisory dependency audit + docs build; Node steps + Docker job commented), Dependabot auto-patching, publish/release + OpenSSF Scorecard + devcontainer (build + verify) workflows, weekly dependency-audit and external-link-check workflows that track findings in one issue each and close it on a clean run, issue/PR + code-of-conduct + security templates |
| `pyproject.toml`, `ci/`, `.python-version` | Python packaging + tool config (ruff, pytest, pyright, codespell), src layout. `ci/requirements.txt` exact-pins the tools that only run the gate, and the one uv version CI, the devcontainer and `make` all use, each with its release files' hashes, so an install rejects a download that doesn't match. The tools' own dependencies are not pinned. `ci/release_notes.py` makes the release notes `release.yml` publishes, `ci/versions.py` chooses the image tags `publish-docker.yml` pushes, `ci/changes.py` decides which of `ci.yml`'s gated jobs a change runs, and `ci/dnf-repo-test.sh` and `ci/dnf_repo_server.py` test the repository `dnf-repo.sh` builds. `.python-version` sets the Python of `ci.yml`'s single-version jobs and the weekly audit (the `test` matrix lists its own); `uv venv` and `uv build` read it too |
| `packaging/` | `rpm.sh` and the spec stub for the RPM each GitHub Release attaches, which `.github/workflows/rpm.yml` builds and installs, `dnf.repo` and `RPM-GPG-KEY`, the dnf repository's definition and public key, which the RPM installs, `dnf-repo.sh`, which signs RPMs and builds signed dnf repository metadata for them, and `fedora.Containerfile`, which pins the Fedora image those jobs run in for Dependabot to update its digest |
| `src/`, `tests/` | The package (src layout, PEP 561 typed) and its tests; the template ships a CLI entry point and logging setup |
| `Makefile`, `.pre-commit-config.yaml` | Task runner (`make install`/`lint`/`fix`/`test`/`check`/`docs`, backed by [uv](https://docs.astral.sh/uv/), installing into the checkout's `.venv`, else the active environment, else the devcontainer's system Python) + the single lint source, whose hooks `make lint` and CI both run, and the source of ruff's and codespell's versions |
| `docs/`, `.readthedocs.yaml.example` | Sphinx docs site (Markdown via MyST, API reference from docstrings); `make docs` builds it. [Publishing targets](#publishing-targets) says how to publish it |
| `AGENTS.md` | Instructions every coding agent reads (Claude Code through `CLAUDE.md`): points to the project rules; corrections, verification commands, skill index |
| `Dockerfile`, `.dockerignore` | Minimal Python image stub — pairs with `publish-docker.yml` |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `RELEASING.md` | Keep-a-Changelog skeleton, a Python contributor guide and the release procedure |
| `.env.example`, `.prettierrc` | Env-var template and Prettier config (for JS/TS work) |
| `.editorconfig` | Language-aware formatting — 4-space Python, 2-space JS/TS, tabs for Makefiles |
| `.gitattributes` | Syntax-aware diffs, LF checkout on every platform |
| `.gitignore` | Comprehensive patterns for Node, Python, Docker, IDEs, env files, build artifacts |
| `CLAUDE.md` | Imports `AGENTS.md` for Claude Code; edit `AGENTS.md` instead |
| `GUARDRAILS.md` | Project rules ranked by how firmly each holds (never / ask first / default / preference) — the tiers Liza agents enforce |
| `.scaffold-sync` | The scaffold commit this repository has caught up to ([Record the sync point](#record-the-sync-point)) |
