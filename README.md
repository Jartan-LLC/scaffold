# Project Template

Production-ready project scaffold with a containerized dev environment, GitHub automation, and Claude Code as a development workflow agent.

**Python-first:** linting, typing, tests, packaging, Docker, and docs are wired up and active out of the box (Node/JS is a supported second). Using another stack? Everything Python is stubbed and clearly deletable — see [docs/onboard.md](docs/onboard.md#not-a-python-project).

## Getting Started

Run `/onboard` in Claude Code to set up this template for your project. It will interview you, configure all the files, and tell you which manual steps remain. To set up by hand instead, follow the checklist in [docs/onboard.md](docs/onboard.md).

## What's Included

| Area | Contents |
|------|----------|
| `.devcontainer/` | Reproducible dev environment: Python, Node.js, Go, Docker, GitHub CLI, Claude Code and [Liza](.devcontainer/liza/README.md) |
| `.claude/` | Claude Code plugins and the `/onboard` setup command |
| `.github/` | CI, Dependabot auto-updates, release and publish workflows, security scanning, issue/PR templates |
| `pyproject.toml`, `src/app/`, `tests/` | A minimal typed Python package with tests, so CI is green on first fork |
| `Makefile`, `.pre-commit-config.yaml` | `make install`, `make check` and friends; the lint hooks CI also runs |
| `docs/` | Sphinx docs site in Markdown |
| `Dockerfile` | Minimal image stub for `publish-docker.yml` |
| `CLAUDE.md`, `GUARDRAILS.md`, `AGENTS.md` | Agent instructions and the project rules, by tier |
| `LICENSE.*`, `CHANGELOG.md`, `CONTRIBUTING.md` | License templates and project skeletons |
| Editor and git config | `.editorconfig`, `.gitattributes`, `.gitignore`, `.prettierrc`, `.env.example` |

Every file, and how the parts work: [docs/scaffold.md](docs/scaffold.md). To pull in later
template improvements, see [Syncing template updates](docs/scaffold.md#syncing-template-updates).
