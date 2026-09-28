# About this template

How the template's parts work and how to keep them current. Unlike `onboard.md`, this page
stays after setup.

## What's included

| Area | Contents |
|------|----------|
| `.devcontainer/` | Reproducible dev environment — Python 3.12, Node.js LTS, Go, Docker, GitHub CLI, desktop-lite; plus Claude Code CLI and codebase-memory-mcp (structural code graph, best-effort), both installed via `post-create.sh`, and Liza (`.devcontainer/liza/README.md`; pinned; activation and its agent toolchain are on by default, each with an opt-out switch). `post-create.sh` also runs `make install`, which installs the project's dependencies into the system Python, as CI does: `containerEnv` sets `UV_SYSTEM_PYTHON`, so the container has no project `.venv` |
| `.claude/` | Claude Code configuration — enabled plugins (skills & agents from the grimoire marketplace) and the `/onboard` setup command |
| `.github/` | CI pipeline (active lint incl. workflow security lint via actionlint/zizmor, + Python typecheck/test/build + advisory dependency audit + docs build; Node steps + Docker job commented), Dependabot auto-patching, publish/release + OpenSSF Scorecard + devcontainer (build + verify) workflows, weekly dependency-audit and external-link-check workflows that track findings in one issue each and close it on a clean run, issue/PR + code-of-conduct + security templates |
| `pyproject.toml`, `ci/requirements.txt`, `.python-version` | Python packaging + tool config (ruff, pytest, pyright, codespell) — minimal src-layout stub; rename or delete. `ci/requirements.txt` exact-pins the tools that only run the gate, and the one uv version CI, the devcontainer and `make` all use. `.python-version` sets the Python of `ci.yml`'s single-version jobs and the weekly audit (the `test` matrix lists its own); `uv venv` and `uv build` read it too |
| `src/app/`, `tests/` | Placeholder package (CLI entry point + logging setup, PEP 561 typed) + smoke/logging tests so CI is green on first fork |
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
| `LICENSE.*` | License templates (MIT, Apache-2.0, AGPL-3.0, proprietary) — pick one during onboarding |

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

On by default. To opt out, set the `ACTIVATE_LIZA` and/or `INSTALL_LIZA_TOOLS` default in
`devcontainer.json` to `false`. A container built before the change keeps what already ran;
undo it with `bash .devcontainer/liza/deactivate.sh` (activation) or
`bash .devcontainer/liza/deactivate.sh --tools` (toolchain). To remove Liza entirely, follow
"Removing Liza" in `.devcontainer/liza/README.md`.

## CI

`ci.yml`'s `lint`, `typecheck`, `test`, `build` and `docs` jobs gate the `check`
aggregator; `audit` runs but is advisory. Removing a gating job also means removing its
`check.needs` and results entries. To add the `docker` or `integration-tests` job,
uncomment it and add it to both. The Node checks are commented steps inside `lint`.

In `.github/dependabot.yml`, remove the ecosystems you don't use, add the ones you need,
and adjust `directory` where manifests aren't at the root.
Dependabot labels its PRs `major`, `minor` or `patch` only if those labels exist:

```bash
gh label create major --color B60205 --description "Major version update" --force
gh label create minor --color FBCA04 --description "Minor version update" --force
gh label create patch --color 0E8A16 --description "Patch version update" --force
```

## Publishing

Nothing publishes until you push a `v*` tag. Delete the workflows you won't use, with their
stubs.

| Workflow | Needs |
|---|---|
| `release.yml` | nothing; creates a GitHub Release with generated notes |
| `publish-pypi.yml` | the package rename; a `pypi` environment (`gh api -X PUT repos/{owner}/{repo}/environments/pypi`) with [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) configured for it; optionally uncomment its tag-vs-version check |
| `publish-docker.yml` | a real `Dockerfile` entrypoint; a `ghcr` environment (`gh api -X PUT repos/{owner}/{repo}/environments/ghcr`), with required reviewers to gate publishing |

Docker images are tagged `X.Y.Z` and `X.Y`; `latest` moves only when the tag is the highest
release.

To publish the docs, pick one: GitHub Pages (Settings > Pages > Source = "GitHub Actions",
then rename `.github/workflows/pages.yml.example` to `pages.yml`), or Read the Docs (rename
`.readthedocs.yaml.example` to `.readthedocs.yaml` and import the repo there).
