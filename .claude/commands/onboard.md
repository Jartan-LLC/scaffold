---
description: Set up this template for your project
---

# Onboard

Configure this template repo for a new project.

## Process

### 1. Prerequisites

Check `gh auth status`. If not authenticated, tell the user to run `gh auth login` before continuing — onboarding uses `gh` commands for repo configuration.

### 2. Read `README.md`

Read its post-fork checklist and `docs/onboard.md`, which details each item (`docs/scaffold.md` covers the parts that stay, such as Liza, CI and publishing). They are the source of truth for what needs to change.

### 3. Interview

Ask the user in a single message for: project name, one-line description, primary language/framework, deployment target, GitHub org/repo, GitHub username, author/full name (for `LICENSE` + `docs/conf.py`), the Python package/import name if Python (for the `src/app` rename), contacts for conduct and security reports (one address, or two if they differ), noting that both are published publicly, so they should give addresses they are willing to publish, build/test/lint commands, license (MIT, Apache-2.0, proprietary, etc.), any version corrections for training data, and whether to keep Liza (activated with its agent toolchain by default; they can turn off either, or remove it — see `.devcontainer/liza/README.md`). List the installed plugin skills/agents (from `enabledPlugins` in `.claude/settings.json`) so the user can choose which to disable via `skillOverrides`.

### 4. Confirm

Summarize what you understood and what changes you'll make. Wait for the user to confirm before proceeding.

### 5. Apply

Work through every Required checklist item that can be automated, following `docs/onboard.md` and `docs/scaffold.md` for how and the interview for the values. Also:

- Replace the template README with a project README
- License: keep the chosen `LICENSE.<type>` as `LICENSE` (`LICENSE.proprietary` is all rights reserved, for private or closed-source work); for a license not among the templates, create it and delete all of them
- Point the `Makefile` at the interview's commands, keeping `make check` as the gate (a Python project's shipped targets already match; for another stack, `docs/onboard.md`, Not a Python project). If the verify command changes, update the Verify section of `CLAUDE.md`
- `SECURITY.md`: always set the contact. Set supported versions and response targets only if the user gave them, and leave any other `TODO(/onboard)` unanswered: a timing commitment the user never chose is worse than an unset field with a stated default
- Liza: activation and the toolchain each ran at container creation unless the host set its switch to `false`. For each the user declines, set its default to `false` in `.devcontainer/devcontainer.json` and run its undo in this clone, a no-op if it never ran (`docs/scaffold.md`, Liza)
- Create the Dependabot `major`/`minor`/`patch` labels (`docs/onboard.md`, Dependabot labels)
- Once every item is done, delete `docs/onboard.md` and its entry in `docs/index.md`, unless the non-Python teardown already removed them

For questions the user didn't have answers to (e.g., version corrections, verify commands), leave the placeholder comments in place — they are written so that Claude will fill them in naturally when the information is discovered during normal development. Only replace placeholders that have actual answers.

### 6. Manual Steps

Present both the Required items that need manual action (enabling private vulnerability reporting) and the Recommended checklist items that require manual action in GitHub Settings. Call out **private vulnerability reporting** (Settings > Security) by name: until it is on, the advisory form `.github/SECURITY.md` sends every reporter to does not exist.

### 7. Cleanup

Ask the user if they want to delete this command file (`.claude/commands/onboard.md`). If yes, delete it.
