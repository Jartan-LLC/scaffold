# About this template

How the template's parts work and how to keep them current. This page stays useful after
setup.

## What's included

| Area | Contents |
|------|----------|
| `.devcontainer/` | Reproducible dev environment — Python 3.12, Node.js LTS, Docker, GitHub CLI, desktop-lite, and the [enchantments](https://github.com/Jartan-LLC/enchantments) Features: Claude Code, the GitHub CLI login, grimoire's plugins, Liza and its agent toolchain. The grimoire Feature installs its plugins at local scope in each clone, skipping any that the repo's `.claude/settings.json` or the clone's `settings.local.json` sets to `false`; `claude plugins disable <id>@grimoire --scope local` sets it for one clone. To drop a Feature, follow the Removal section on its page, where it has one ([the Features list](https://github.com/Jartan-LLC/enchantments#features) links each page), then remove its entry and its `devcontainer-lock.json` key. `post-create.sh` runs `make install`, which installs the project's dependencies into the system Python, as CI does: `containerEnv` sets `UV_SYSTEM_PYTHON`, so the container has no project `.venv` |
| `.claude/` | Claude Code configuration — enabled plugins (skills & agents from the grimoire marketplace) |
| `.github/` | CI pipeline (active lint incl. workflow security lint via actionlint/zizmor, + Python typecheck/test/build + advisory dependency audit + docs build; Node steps + Docker job commented), Dependabot auto-patching, publish/release + OpenSSF Scorecard + devcontainer (build + verify) workflows, weekly dependency-audit and external-link-check workflows that track findings in one issue each and close it on a clean run, issue/PR + code-of-conduct + security templates |
| `pyproject.toml`, `ci/requirements.txt`, `.python-version` | Python packaging + tool config (ruff, pytest, pyright, codespell), src layout. `ci/requirements.txt` exact-pins the tools that only run the gate, and the one uv version CI, the devcontainer and `make` all use. `.python-version` sets the Python of `ci.yml`'s single-version jobs and the weekly audit (the `test` matrix lists its own); `uv venv` and `uv build` read it too |
| `src/`, `tests/` | The package (src layout, PEP 561 typed) and its tests; the template ships a CLI entry point and logging setup |
| `Makefile`, `.pre-commit-config.yaml` | Task runner (`make install`/`lint`/`fix`/`test`/`check`/`docs`, backed by [uv](https://docs.astral.sh/uv/), installing into the checkout's `.venv`, else the active environment, else the devcontainer's system Python) + the single lint source (ruff, codespell, shellcheck, markdownlint, lychee, actionlint, zizmor, hygiene) that `make lint` and CI both run, and the source of ruff's and codespell's versions |
| `docs/`, `.readthedocs.yaml.example` | Sphinx docs site (Markdown via MyST, API reference from docstrings); `make docs` builds it. Publish via `pages.yml.example` (GitHub Pages) or ReadTheDocs |
| `AGENTS.md` | Symlink to `CLAUDE.md` for vendor-neutral agent tools (Cursor, Copilot, …); tools that don't follow `@` imports won't load `GUARDRAILS.md` |
| `Dockerfile`, `.dockerignore` | Minimal Python image stub — pairs with `publish-docker.yml` |
| `CHANGELOG.md`, `CONTRIBUTING.md` | Keep-a-Changelog skeleton and a Python contributor guide |
| `.env.example`, `.prettierrc` | Env-var template and Prettier config (for JS/TS work) |
| `.editorconfig` | Language-aware formatting — 4-space Python, 2-space JS/TS, tabs for Makefiles |
| `.gitattributes` | Syntax-aware diffs, LF checkout on every platform |
| `.gitignore` | Comprehensive patterns for Node, Python, Docker, IDEs, env files, build artifacts |
| `CLAUDE.md` | Imports the project rules; corrections, verification commands, skill index |
| `GUARDRAILS.md` | Project rules ranked by how firmly each holds (never / ask first / default / preference) — the tiers Liza agents enforce |

## Syncing template updates

You can still pull in later improvements to the template. How depends on how your repository started.

```bash
# One-time, either way: add the template as an 'upstream' remote
git remote add upstream https://github.com/Jartan-LLC/scaffold.git  # this template's repo
git fetch upstream
```

**If you used *Use this template*** — the button on the template's GitHub page — GitHub started your history
fresh, so there is nothing to merge: `git merge upstream/main` stops at `fatal: refusing to merge
unrelated histories`. Port changes by hand instead, and keep the newest upstream commit you have
dealt with — ported or deliberately skipped — in `.scaffold-sync` at your repository root:

```bash
# First time only: the template commit your repository was created from
git rev-list -1 --before="$(git log --reverse --format=%cI | head -1)" upstream/main > .scaffold-sync

git log --oneline --reverse "$(cat .scaffold-sync)"..upstream/main  # not yet dealt with, oldest first
git show <sha>                          # the change to port; apply the equivalent by hand
echo <sha> > .scaffold-sync             # once everything up to <sha> is ported or skipped
```

Commit `.scaffold-sync` with the port, so the file always matches what the repository contains.

**If you forked this repository**, the history is shared and the merge works:

```bash
git checkout -b template-update
git merge upstream/main   # resolve conflicts, keeping your customizations
```

Open a PR either way, so CI runs before the changes land.

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

`ci.yml`'s `lint`, `typecheck`, `test`, `build` and `docs` jobs gate the `check`
aggregator; `audit` runs but is advisory. Removing a gating job also means removing its
`check.needs` and results entries. To add the `docker` or `integration-tests` job,
uncomment it and add it to both. The Node checks are commented steps inside `lint`:
uncomment them there, with no `check` change needed.

In `.github/dependabot.yml`, remove the ecosystems you don't use, add the ones you need,
and adjust `directory` where manifests aren't at the root.

## Publishing

Nothing publishes until you push a `v*` tag. Keep `release.yml` even if you publish no
package or image: it is language-agnostic. Delete the publish workflows you won't use, with
their stubs.

| Workflow | Needs |
|---|---|
| `release.yml` | nothing; creates a GitHub Release with generated notes |
| `publish-pypi.yml` | the package rename; a `pypi` environment (`gh api -X PUT repos/{owner}/{repo}/environments/pypi`, which also clears the GitHub Actions VS Code extension's "environment `pypi` is not valid" warning) with [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) configured for it, so no token secret is stored. It fails on a tag until both are done. Optionally uncomment its tag-vs-version check |
| `publish-docker.yml` | a real `Dockerfile` entrypoint; a `ghcr` environment (`gh api -X PUT repos/{owner}/{repo}/environments/ghcr`), with required reviewers to gate publishing. Publishes multi-arch images to `ghcr.io/OWNER/REPO` with the built-in `GITHUB_TOKEN`, no secret needed |

Docker images are tagged `X.Y.Z` and `X.Y`; `latest` moves only when the tag is the highest
release.

To publish the docs, pick one: GitHub Pages for a single version (Settings > Pages >
Source = "GitHub Actions", then rename `.github/workflows/pages.yml.example` to
`pages.yml`), or Read the Docs for versioned docs (rename `.readthedocs.yaml.example` to
`.readthedocs.yaml` and import the repo there). The docs build is checked on every PR either
way.
