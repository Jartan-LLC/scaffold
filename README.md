# Project Template

Production-ready project scaffold with a containerized dev environment, GitHub automation, and Claude Code as a development workflow agent.

**Python-first:** linting, typing, tests, packaging, Docker, and docs are wired up and active out of the box (Node/JS is a supported second). Using another stack? Everything Python is stubbed and clearly deletable — see the checklist below.

## Getting Started

Run `/onboard` in Claude Code to set up this template for your project. It will interview you, configure all the files, and tell you which manual steps remain.

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

## Post-Fork Checklist

If you prefer to set up manually instead of using `/onboard`:

### Required

Details for each item: [docs/onboard.md](docs/onboard.md).

- [ ] Fill in `CLAUDE.md` and `GUARDRAILS.md` ([details](docs/onboard.md#project-instructions))
- [ ] Adapt the devcontainer and the `Makefile`'s `deps` target to your stack ([details](docs/onboard.md#devcontainer))
- [ ] Keep, turn off or remove Liza ([details](docs/scaffold.md#liza))
- [ ] Add your stack's patterns to `.gitignore` and rules to `.editorconfig`
- [ ] Set owners in `.github/CODEOWNERS`
- [ ] Set the security and conduct contacts, and enable private vulnerability reporting ([details](docs/onboard.md#security-and-conduct-contacts))
- [ ] Replace the `ORG/REPO` placeholders, except in `.lycheeignore`, where you delete the line ([details](docs/onboard.md#orgrepo-placeholders))
- [ ] Rename the Python package ([details](docs/onboard.md#python-package)), or tear down Python ([details](docs/onboard.md#not-a-python-project))
- [ ] Replace `tests/test_smoke.py` with real tests
- [ ] Prune `.github/workflows/ci.yml` and `.github/dependabot.yml` to your stack ([details](docs/scaffold.md#ci))
- [ ] Update the docs site ([details](docs/onboard.md#docs-site))
- [ ] Create `LICENSE` from one of the `LICENSE.*` templates (fill in `[year]` and `[fullname]`), and delete the rest
- [ ] Switch off plugin skills that don't fit your stack ([details](docs/onboard.md#claude-settings))

### Recommended

- [ ] Set up publishing: package, image, docs site ([details](docs/scaffold.md#publishing))
- [ ] Create the `major`/`minor`/`patch` labels Dependabot adds to its PRs ([details](docs/onboard.md#dependabot-labels))
- [ ] Enable GitHub Discussions (Settings > General > Features) — issue template config links to it
- [ ] Enable CodeQL default setup (Settings > Security > Code scanning)
- [ ] Delete `.github/workflows/scorecard.yml` if you don't want an OpenSSF score (it skips on private repos)
- [ ] Enable secret scanning with push protection (Settings > Security > Secret Protection)
- [ ] Configure branch ruleset for `main` — require PR reviews, require CI to pass, block force pushes
- [ ] Enable auto-merge (Settings > General > Allow auto-merge) — Dependabot minor/patch PRs auto-merge after CI passes

### Cleanup

- [ ] Replace this README with your own
- [ ] Delete `docs/onboard.md` and its entry in `docs/index.md`
- [ ] Delete `.claude/commands/onboard.md`
