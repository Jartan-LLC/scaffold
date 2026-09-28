# Project Template

Production-ready project scaffold with a containerized dev environment, GitHub automation, and Claude Code as a development workflow agent.

**Python-first:** linting, typing, tests, packaging, Docker, and docs are wired up and active out of the box (Node/JS is a supported second). Using another stack? Everything Python is stubbed and clearly deletable — see the checklist below.

## Getting Started

Run `/onboard` in Claude Code to set up this template for your project. It will interview you, configure all the files, and tell you which manual steps remain.

## Syncing Template Updates

You can still pull in later improvements to the template. How depends on how your repository started.

```bash
# One-time, either way: add the template as an 'upstream' remote
git remote add upstream https://github.com/Jartan-LLC/scaffold.git  # this template's repo
git fetch upstream
```

**If you used *Use this template*** — the button on this repository — GitHub started your history
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

## What's Included

| Area | Contents |
|------|----------|
| `.devcontainer/` | Reproducible dev environment — Python 3.12, Node.js LTS, Go, Docker, GitHub CLI, desktop-lite; plus Claude Code CLI and codebase-memory-mcp (structural code graph, best-effort), both installed via `post-create.sh`, and [Liza](.devcontainer/liza/README.md) (pinned; activation and its agent toolchain are on by default, each with an opt-out switch). `post-create.sh` also runs `make install`, which installs the project's dependencies into the system Python, as CI does: `containerEnv` sets `UV_SYSTEM_PYTHON`, so the container has no project `.venv` |
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

## Post-Fork Checklist

If you prefer to set up manually instead of using `/onboard`:

### Required

Details for each item: [docs/scaffold.md](docs/scaffold.md).

- [ ] Fill in `CLAUDE.md` and `GUARDRAILS.md` ([details](docs/scaffold.md#project-instructions))
- [ ] Adapt the devcontainer and the `Makefile`'s `deps` target to your stack ([details](docs/scaffold.md#devcontainer))
- [ ] Keep, turn off or remove Liza ([details](docs/scaffold.md#liza))
- [ ] Add your stack's patterns to `.gitignore` and rules to `.editorconfig`
- [ ] Set owners in `.github/CODEOWNERS`
- [ ] Set the security and conduct contacts, and enable private vulnerability reporting ([details](docs/scaffold.md#security-and-conduct-contacts))
- [ ] Replace the `ORG/REPO` placeholders ([details](docs/scaffold.md#orgrepo-placeholders))
- [ ] Rename the Python package ([details](docs/scaffold.md#python-package)), or tear down Python ([details](docs/scaffold.md#not-a-python-project))
- [ ] Replace `tests/test_smoke.py` with real tests
- [ ] Prune `.github/workflows/ci.yml` and `.github/dependabot.yml` to your stack ([details](docs/scaffold.md#ci))
- [ ] Update the docs site ([details](docs/scaffold.md#docs-site))
- [ ] Create `LICENSE` from one of the `LICENSE.*` templates (fill in `[year]` and `[fullname]`), and delete the rest
- [ ] Switch off plugin skills that don't fit your stack ([details](docs/scaffold.md#claude-settings))

### Recommended

- [ ] Set up publishing: package, image, docs site ([details](docs/scaffold.md#publishing))
- [ ] Enable GitHub Discussions (Settings > General > Features) — issue template config links to it
- [ ] Enable CodeQL default setup (Settings > Security > Code scanning)
- [ ] Delete `.github/workflows/scorecard.yml` if you don't want an OpenSSF score (it skips on private repos)
- [ ] Enable secret scanning with push protection (Settings > Security > Secret Protection)
- [ ] Configure branch ruleset for `main` — require PR reviews, require CI to pass, block force pushes
- [ ] Enable auto-merge (Settings > General > Allow auto-merge) — Dependabot minor/patch PRs auto-merge after CI passes

### Cleanup

- [ ] Replace this README with your own
- [ ] Delete `docs/scaffold.md` and its entry in `docs/index.md`
- [ ] Delete `.claude/commands/onboard.md`
