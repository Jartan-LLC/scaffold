# Project Template

Production-ready project scaffold with a containerized dev environment, GitHub automation, and Claude Code as a development workflow agent.

**Python-first:** linting, typing, tests, packaging, Docker, and docs are wired up and active out of the box (Node/JS is a supported second). Using another stack? Everything Python is stubbed and clearly deletable — see the checklist below.

## Getting Started

Run `/onboard` in Claude Code to set up this template for your project. It will interview you, configure all the files, and tell you which manual steps remain.

## Syncing template updates

After you fork, you can still pull in later improvements to the template:

```bash
# One-time: add the template as an 'upstream' remote
git remote add upstream https://github.com/Jartan-LLC/scaffold.git

# Each time you want updates
git fetch upstream
git checkout -b template-update
git merge upstream/main   # resolve conflicts, keeping your customizations
```

Open a PR from `template-update` so CI runs before the changes land.

## What's Included

| Area | Contents |
|------|----------|
| `.devcontainer/` | Reproducible dev environment — Python 3.12, Node.js LTS, Docker, GitHub CLI, desktop-lite, Claude Code CLI, codebase-memory-mcp (structural code graph) |
| `.claude/` | Claude Code plugins and configuration — dev workflow, code review, session memory, Python patterns, recursive development, token efficiency |
| `.github/` | CI pipeline (active lint incl. workflow security lint via actionlint/zizmor, + Python typecheck/test/build + dependency audit + docs build; Node steps + Docker job commented), Claude Code as CI agent (@claude in issues/PRs), Dependabot auto-patching, publish/release + OpenSSF Scorecard workflows, issue/PR + code-of-conduct + security templates |
| `pyproject.toml` | Python packaging + tool config (ruff, pytest, pyright, codespell) — minimal src-layout stub; rename or delete |
| `src/app/`, `tests/` | Placeholder package (CLI entry point + logging setup, PEP 561 typed) + smoke/logging tests so CI is green on first fork |
| `Makefile`, `.pre-commit-config.yaml` | Task runner (`make lint`/`test`/`check`/`docs`) + the single lint source (ruff, codespell, shellcheck, markdownlint, actionlint, zizmor, hygiene) that `make lint` and CI both run |
| `docs/`, `.readthedocs.yaml.example` | Sphinx docs site (Markdown via MyST, API reference from docstrings); `make docs` builds it. Publish via `pages.yml.example` (GitHub Pages) or ReadTheDocs |
| `AGENTS.md` | Symlink to `CLAUDE.md` so vendor-neutral agent tools (Cursor, Copilot, …) read the same rules |
| `Dockerfile`, `.dockerignore` | Minimal Python image stub — pairs with `publish-docker.yml` |
| `CHANGELOG.md`, `CONTRIBUTING.md` | Keep-a-Changelog skeleton and a Python contributor guide |
| `.env.example`, `.prettierrc` | Env-var template and Prettier config (for JS/TS work) |
| `.editorconfig` | Language-aware formatting — 4-space Python, 2-space JS/TS, tabs for Makefiles |
| `.gitattributes` | Syntax-aware diffs for 20+ languages, binary normalization for lock files |
| `.gitignore` | Comprehensive patterns for Node, Python, Docker, IDEs, env files, build artifacts |
| `CLAUDE.md` | Project rules, anti-patterns, verification commands, skill index |
| `LICENSE.*` | Three license templates (MIT, Apache-2.0, AGPL-3.0) — pick one during onboarding |

## Post-Fork Checklist

If you prefer to set up manually instead of using `/onboard`:

### Required

- [ ] Update `CLAUDE.md` — replace placeholder comments:
  - Project name and description (the `# Project Name` heading and the description line under it)
  - Corrections with any version-specific overrides for your stack
- [ ] Update `CLAUDE.md` Skills section — add project-specific skills/conventions as they emerge
- [ ] Update `.devcontainer/devcontainer.json` — change the desktop-lite password, add/remove language features and extensions for your stack
- [ ] Update `.devcontainer/post-create.sh` — add dependency installation for your stack
- [ ] Update `.devcontainer/post-start.sh` — add commands that should run on each container start (Docker socket fix and Codespaces env overrides are included)
- [ ] Update `.gitignore` — add language-specific patterns for your stack
- [ ] Update `.editorconfig` — adjust formatting rules for your language (e.g., tabs for Go)
- [ ] Update `.github/CODEOWNERS` — uncomment and set owner usernames/teams
- [ ] Update `.github/SECURITY.md` — set supported versions and response timeline
- [ ] Update `.github/CODE_OF_CONDUCT.md` — set the enforcement contact (replace `[INSERT CONTACT METHOD]`)
- [ ] Update `.github/ISSUE_TEMPLATE/config.yml` — replace `ORG/REPO` in contact link URLs with your GitHub org and repo name
- [ ] Update `CHANGELOG.md` — replace `ORG/REPO` in the `[Unreleased]` link with your GitHub org and repo (otherwise the link 404s)
- [ ] Update `.github/dependabot.yml` — remove ecosystems you don't use, add ones you need, adjust directories if not at root
- [ ] Create the `dependency` label — `gh label create dependency --color 0366d6 --description "Dependency updates"` (required by dependabot config)
- [ ] Rename the Python package — set `pyproject.toml` `name` + `description`, rename the `src/app/` directory, and update `[tool.hatch.build.targets.wheel]` `packages` to match (`/onboard` does this; skip the `packages` edit and `python -m build` fails). **Not a Python project?** Delete `pyproject.toml`, `src/`, `tests/`, the docs stack (`docs/`, `.readthedocs.yaml.example`, `.github/workflows/pages.yml.example`), `.github/workflows/publish-pypi.yml`, and — if not containerized — `Dockerfile`, `.dockerignore`, `.github/workflows/publish-docker.yml`; adapt `CONTRIBUTING.md` (rewrite the `pip install` setup and the "Requires Python 3.12+" line); trim the `ruff` hook from `.pre-commit-config.yaml` (keep the language-agnostic hooks — shellcheck, markdownlint, actionlint, zizmor, hygiene); repoint the `Makefile` targets at your stack's lint/format/typecheck/test/build commands so `make check` stays your one verify gate; in `.github/workflows/ci.yml` remove the `typecheck`/`test`/`build`/`audit`/`docs` jobs (and their `check.needs` + results entries) — the `lint` job just runs pre-commit and stays.
- [ ] Replace `tests/test_smoke.py` with real tests — it only exists so the `test` CI job is green out of the box
- [ ] Review `.github/workflows/ci.yml` — the `lint`/`typecheck`/`test`/`build`/`audit`/`docs` jobs are ACTIVE and pass against the shipped stubs. Delete jobs you don't need (and their entries in the `check` aggregator). To enable extras, uncomment the `docker`/`integration-tests` jobs and add each to `check.needs` + the results array; the Node checks are commented *steps inside the `lint` job* (uncomment them there — no `check` change needed)
- [ ] Docs — set `project`/`author`/`project_copyright` in `docs/conf.py`; write the `docs/index.md` landing page (replace the `# Project Docs` title + `TODO(/onboard)`); update the `pip install app` line in `docs/getting-started.md` to the renamed package; after renaming the package, uncomment the `automodule` block in `docs/reference.md` and point it at your modules (`/onboard` does this)
- [ ] Create a `LICENSE` file — rename one of the included templates (`LICENSE.MIT`, `LICENSE.Apache-2.0`, `LICENSE.AGPL-3.0`) to `LICENSE`, fill in `[year]` and `[fullname]`, delete the others
- [ ] Add `skillOverrides` to `.claude/settings.json` — disable installed plugin skills that don't match your stack
- [ ] Add secrets to your repo:
  - `ANTHROPIC_API_KEY` — for the Claude Code workflow
  - `APP_ID` — GitHub App ID
  - `APP_PRIVATE_KEY` — GitHub App private key
  - **GitHub App setup**:
    1. Create a GitHub App at <https://github.com/settings/apps>
    2. Under Permissions, grant Contents, Issues, and Pull Requests (Read & Write)
    3. Under Webhook, uncheck "Active" (not needed for this workflow)
    4. Install the app on your repo
    5. Store the App ID and a generated private key as repo secrets

### Recommended

- [ ] Set up publishing — the release/publish workflows are opt-in: nothing runs until you push a `v*` tag.
  - **`release.yml`** — creates a GitHub Release with auto-generated notes on every `v*` tag. Language-agnostic; keep it even if you publish no package or image.
  - **`publish-pypi.yml`** — a stub `pyproject.toml` is included (rename the package first). Create a `pypi` [Environment](https://docs.github.com/actions/deployment/targeting-different-environments) and configure [PyPI Trusted Publishing (OIDC)](https://docs.pypi.org/trusted-publishers/) for it — no token secret. Optionally uncomment the tag-vs-version check.
  - **`publish-docker.yml`** — a stub `Dockerfile` is included (give it a real entrypoint). Publishes multi-arch images to `ghcr.io/OWNER/REPO` using the built-in `GITHUB_TOKEN` — no secret needed.
  - All trigger on `v*` tags. `publish-pypi.yml` still fails until you rename the package and configure PyPI Trusted Publishing; delete whichever publish workflow (and its stub) you don't need.
- [ ] Enable GitHub Discussions (Settings > General > Features) — issue template config links to it
- [ ] Enable CodeQL default setup (Settings > Security > Code scanning)
- [ ] OpenSSF Scorecard (`.github/workflows/scorecard.yml`) needs a **public** repo to publish its score/badge — delete the workflow if the repo is private
- [ ] Publish docs (optional) — **GitHub Pages**: set Settings > Pages > Source = "GitHub Actions", then rename `.github/workflows/pages.yml.example` → `pages.yml` (single-version). **Versioned**: rename `.readthedocs.yaml.example` → `.readthedocs.yaml` and import the repo at readthedocs.org. Pick one; the docs *build* is already checked on every PR either way
- [ ] Enable secret scanning with push protection (Settings > Security > Secret Protection)
- [ ] Configure branch ruleset for `main` — require PR reviews, require CI to pass, block force pushes
- [ ] Enable auto-merge (Settings > General > Allow auto-merge) — Dependabot minor/patch PRs auto-merge after CI passes
- [ ] Review `.github/workflows/claude.yml` — uses `--dangerously-skip-permissions` which grants Claude unrestricted tool access in CI

### Cleanup

- [ ] Replace this README with your own
- [ ] Delete `.claude/commands/onboard.md`
