---
description: Set up this template for your project
---

# Onboard

Configure this template repo for a new project.

## Process

### 1. Prerequisites

Check `gh auth status`. If not authenticated, tell the user to run `gh auth login` before continuing — onboarding uses `gh` commands for repo configuration.

### 2. Read `README.md`

Read the post-fork checklist. This is the source of truth for what needs to change.

### 3. Interview

Ask the user in a single message for: project name, one-line description, primary language/framework, deployment target, GitHub org/repo, GitHub username, author/full name (for `LICENSE` + `docs/conf.py`), the Python package/import name if Python (for the `src/app` rename), the code-of-conduct enforcement contact, build/test/lint commands, license (MIT, Apache-2.0, proprietary, etc.), and any version corrections for training data. List the installed plugin skills/agents (from `enabledPlugins` in `.claude/settings.json`) so the user can choose which to disable via `skillOverrides`.

### 4. Confirm

Summarize what you understood and what changes you'll make. Wait for the user to confirm before proceeding.

### 5. Apply

Work through every Required checklist item that can be automated. Also:

- Replace the template README with a project README
- License: rename the chosen `LICENSE.<type>` file to `LICENSE`, delete the others, and fill in `[year]` and `[fullname]`. Available: `LICENSE.MIT`, `LICENSE.Apache-2.0`, `LICENSE.AGPL-3.0`. If the user wants a different license or proprietary, delete all three and create the appropriate file.
- Update `.devcontainer/devcontainer.json` — change the `desktop-lite` `password`, add/remove language features and extensions to match the chosen stack
- Update `.devcontainer/post-create.sh` — add dependency installation for the chosen stack (e.g., `go mod download`, `cargo build`)
- Update `.devcontainer/post-start.sh` — add commands that should run on each container start
- Update `.gitignore` — add language-specific patterns for the chosen stack
- Update `.editorconfig` — adjust formatting rules for the chosen language (e.g., tabs for Go)
- If Python: rename the package stub — set `pyproject.toml` `name` + `description`, rename the `src/app/` directory to the import name (update `[tool.hatch.build.targets.wheel]` `packages` to match), fix the `prog=` and `python -m app` references in `src/app/__main__.py` (or replace that stub) and the `Dockerfile` `CMD` hint, update the `from app.log import …` in `tests/test_log.py`, and replace `tests/test_smoke.py` with a real test. If not Python: follow the README's **Not a Python project?** teardown (delete the Python artifacts, adapt `CONTRIBUTING.md`, trim the `ruff` pre-commit hook, prune the Python `ci.yml` jobs — the `lint` job stays)
- The `Makefile` stays in every fork — it's the language-agnostic verify entry point. Point its `lint`/`typecheck`/`test`/`build` targets at the build/test/lint commands from the interview (keep `make check` as the aggregate gate); for a Python project the shipped targets already match, so only edit if the user's commands differ
- Fill in `CHANGELOG.md` — replace `ORG/REPO` in the `[Unreleased]` link with the GitHub org/repo
- Replace `ORG/REPO` in `.github/ISSUE_TEMPLATE/config.yml` contact links with the GitHub org/repo
- Set the code-of-conduct enforcement contact in `.github/CODE_OF_CONDUCT.md` (replace `[INSERT CONTACT METHOD]`)
- Docs: set `project`/`author`/`project_copyright` in `docs/conf.py`; write the `docs/index.md` landing page (replace `# Project Docs` + the `TODO(/onboard)` comment); update the `pip install app` line in `docs/getting-started.md` to the renamed package; after the package rename, update the `automodule` module names in `docs/reference.md` (replace `app.log`/`app.__main__` with the renamed package's modules — the docs build fails if left stale)
- Create the `dependency` label used by dependabot: `gh label create dependency --color 0366d6 --description "Dependency updates" 2>/dev/null || true`
- When removing skills, also update any agent files that reference them in their `skills:` frontmatter
- Add `skillOverrides` to `.claude/settings.json` — disable installed plugin skills that don't match the chosen stack. If multiple plugins cover the same domain, keep the more specific one. Keep universal skills enabled. Set disabled skills to `"off"`. Example: `"skillOverrides": { "go-review": "off", "springboot-patterns": "off" }`

For questions the user didn't have answers to (e.g., version corrections, verify commands), leave the placeholder comments in place — they are written so that Claude will fill them in naturally when the information is discovered during normal development. Only replace placeholders that have actual answers.

### 6. Manual Steps

Present both the Required items that need manual action (adding secrets) and the Recommended checklist items that require manual action in GitHub Settings.

### 7. Cleanup

Ask the user if they want to delete this command file (`.claude/commands/onboard.md`). If yes, delete it.
