---
description: Set up this template for your project
---

# Onboard

Configure this template repo for a new project.

## Process

### 1. Read `README.md`

Read the post-fork checklist. This is the source of truth for what needs to change.

### 2. Interview

Ask the user in a single message for: project name, one-line description, primary language/framework, deployment target, GitHub org/repo, GitHub username, build/test/lint commands, license (MIT, Apache-2.0, proprietary, etc.), and any version corrections for training data. List the skills and agents that exist in `.claude/skills/` and `.claude/agents/` so the user can choose which to keep.

### 3. Confirm

Summarize what you understood and what changes you'll make. Wait for the user to confirm before proceeding.

### 4. Apply

Work through every Required checklist item that can be automated. Also:

- Replace the template README with a project README
- Create a `LICENSE` file if the user specified a license
- Update `.devcontainer/devcontainer.json` — add/remove language features and extensions to match the chosen stack
- Update `.devcontainer/setup.sh` — add dependency installation for the chosen stack (e.g., `go mod download`, `cargo build`)
- Update `.gitignore` — add language-specific patterns for the chosen stack
- Update `.editorconfig` — adjust formatting rules for the chosen language (e.g., tabs for Go)
- When removing skills, also update any agent files that reference them in their `skills:` frontmatter

For questions the user didn't have answers to (e.g., version corrections, verify commands), leave the placeholder comments in place — they are written so that Claude will fill them in naturally when the information is discovered during normal development. Only replace placeholders that have actual answers.

### 5. Manual Steps

Present both the Required items that need manual action (adding secrets) and the Recommended checklist items that require manual action in GitHub Settings.

### 6. Cleanup

Ask the user if they want to delete this command file (`.claude/commands/onboard.md`). If yes, delete it.
