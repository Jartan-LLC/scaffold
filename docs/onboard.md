# Setting up the template

The setup checklist, then the details for each item that needs more than a line. `/onboard`
in Claude Code works through it for you. Delete this page (and its entry in `index.md`) at
Cleanup; [`scaffold.md`](scaffold.md) covers what stays useful afterwards.

## Checklist

### Required

- [ ] Fill in `CLAUDE.md` and `GUARDRAILS.md` ([details](#project-instructions))
- [ ] Adapt the devcontainer and the `Makefile`'s `install` target to your stack ([details](#devcontainer))
- [ ] Keep or decline each enchantments Feature ([details](#devcontainer))
- [ ] Add your stack's patterns to `.gitignore` and rules to `.editorconfig`
- [ ] Set owners in `.github/CODEOWNERS`
- [ ] Set the security and conduct contacts, and enable private vulnerability reporting ([details](#security-and-conduct-contacts))
- [ ] Replace the `ORG/REPO` placeholders, except in `.lycheeignore`, where you delete the line ([details](#orgrepo-placeholders))
- [ ] Rename the Python package ([details](#python-package)), or tear down Python ([details](#not-a-python-project))
- [ ] Replace `tests/test_smoke.py` with real tests
- [ ] Prune `.github/workflows/ci.yml` and `.github/dependabot.yml` to your stack ([details](scaffold.md#ci))
- [ ] Update the docs site ([details](#docs-site))
- [ ] Set your license: keep `LICENSE` (MIT) with your own year and name, or replace it with one of the `LICENSE.*` templates (filling in `[year]` and `[fullname]`), then delete the `LICENSE.*` files
- [ ] Switch off plugin skills that don't fit your stack ([details](#claude-settings))

### Recommended

- [ ] Set up publishing: package, image, docs site ([details](scaffold.md#publishing))
- [ ] Create the `major`/`minor`/`patch` labels Dependabot adds to its PRs ([details](#dependabot-labels))
- [ ] Enable GitHub Discussions (Settings > General > Features) — issue template config links to it
- [ ] Enable CodeQL default setup (Settings > Security > Code scanning)
- [ ] Delete `.github/workflows/scorecard.yml` if you don't want an OpenSSF score (it skips on private repos)
- [ ] Enable secret scanning with push protection (Settings > Security > Secret Protection)
- [ ] Configure branch ruleset for `main` — require PR reviews, require CI to pass, block force pushes
- [ ] Enable auto-merge (Settings > General > Allow auto-merge) — Dependabot minor/patch PRs auto-merge after CI passes

### Cleanup

- [ ] Replace `README.md` with your own
- [ ] Delete this page and its entry in `docs/index.md`
- [ ] Delete `.claude/commands/onboard.md`

## Project instructions

- `CLAUDE.md`: replace the `# Project Name` heading and the `<!-- ONE LINE: … -->` comment
  under it; add version-specific overrides for your stack under Corrections; add skills and
  conventions under Skills as they emerge. If your verify command is not `make check`,
  update the Verify section.
- `GUARDRAILS.md`: add project rules as they emerge, at the tier each must hold.

## Devcontainer

- `devcontainer.json`: change the `desktop-lite` password; add or remove Features and
  extensions for your stack.
- For each [enchantments](https://github.com/Jartan-LLC/enchantments) Feature you decline, follow
  the Removal section on its page, if it has one
  ([the Features list](https://github.com/Jartan-LLC/enchantments#features) links each page);
  otherwise remove its entry from `devcontainer.json`. Either way, also remove its key
  from `devcontainer-lock.json`, then rebuild. Also:
  - Declining `claude-code` means declining `grimoire` too (and `codebase-memory-mcp`, if
    you added it), and declining `liza` means declining `liza-toolchain`.
  - Keep the `node` Feature while `grimoire` is declared.
  - To keep a code graph without `liza-toolchain`, declare `codebase-memory-mcp` in its place.
  - A Feature in your VS Code `dev.containers.defaultFeatures` comes back on rebuild, so
    declining it here applies only to contributors who don't set it. Declare `liza` and
    `liza-toolchain` both in `devcontainer.json` or both only in `defaultFeatures`
    ([liza-toolchain](https://github.com/Jartan-LLC/enchantments/blob/main/src/liza-toolchain/README.md)).
- `post-start.sh`: add commands to run on each container start. The Docker socket fix and
  Codespaces environment overrides are already there.
- Dependencies: add your stack's install (for example `go mod download`) to the `Makefile`'s
  `install` target, which runs on a bare host and from `post-create.sh`.

## Python package

Rename the `app` stub to your import name:

1. `pyproject.toml`: set `name` and `description`, and point
   `[tool.hatch.build.targets.wheel]` `packages` at the new directory. Without it the
   build fails.
2. Rename `src/app/`.
3. Update the imports: `from app.log import …` in `src/app/__main__.py` and
   `tests/test_log.py`, `from app.__main__ import …` in `tests/test_smoke.py`.
4. Update the `python -m app` references: `prog=` and the module docstring in `__main__.py`
   (or replace that stub), and the `Dockerfile` `CMD` hint.
5. Update the docs (Docs site, below).

## Not a Python project

Do this after the other Required items: it deletes the docs site. Keep `docs/scaffold.md`,
which reads fine on GitHub without Sphinx, and this page, which Cleanup deletes.

1. Move `[tool.codespell]` from `pyproject.toml` to a `.codespellrc`.
2. Delete `pyproject.toml`, `src/`, `tests/`, everything in `docs/` but `scaffold.md` and this page,
   `.readthedocs.yaml.example`,
   `.github/workflows/pages.yml.example`, `.github/workflows/publish-pypi.yml` and
   `.github/workflows/dependency-audit.yml`. If not containerized, also `Dockerfile`,
   `.dockerignore` and `.github/workflows/publish-docker.yml`.
3. In `.pre-commit-config.yaml`, remove the `ruff-pre-commit` entry. Keep the other hooks.
4. In `.github/workflows/ci.yml`, remove the `typecheck`, `test`, `build`, `audit` and
   `docs` jobs and their `check` entries (`docs/scaffold.md`, CI). `lint` stays.
5. Keep the `Makefile`: it is the verify entry point in every stack. Point its `lint`, `fix`,
   `typecheck`, `test` and `docs` targets at your stack's commands, and replace the Python
   lines in `check` (the `.[dev,docs]` install, `uv build`, `twine check`, `pip-audit`), so
   `make check` stays the one verify gate.
6. In `CONTRIBUTING.md`, rewrite the `make install` setup and the "Requires Python 3.12+ and
   uv" line for your stack.
7. Trim the Python parts of `docs/scaffold.md`.

## Security and conduct contacts

- `.github/SECURITY.md`: set the private security contact. It is published, and it is the
  reporter's only channel when the advisory form is unavailable. Write it in angle
  brackets (`<security@example.org>`); a bare address fails markdownlint. Then delete the
  `unconfigured-contact` block: both markers, the paragraph between them and the blank
  line after the closing marker; keep the paragraph that follows, which stays true once a
  contact is set. Set the supported versions (replacing the commented table hint) and the
  response targets.
- Enable private vulnerability reporting (Settings > Security). Until it is on, the advisory
  form `SECURITY.md` links to does not exist.
- `.github/CODE_OF_CONDUCT.md`: replace `[INSERT CONTACT METHOD]`.

## ORG/REPO placeholders

- `.github/ISSUE_TEMPLATE/config.yml` and the `[Unreleased]` link in `CHANGELOG.md`:
  replace `ORG/REPO` with your org and repo.
- `.lycheeignore`: delete only the `https://github.com/ORG/REPO` line. Replacing it would
  make the link check ignore your own repo. Keep every other line; the `file://`
  advisory-form pattern is permanent.

## Docs site

- `conf.py`: set `project`, `author` and `project_copyright`.
- `index.md`: write the landing page, replacing `# Project Docs` and its `TODO(/onboard)`.
- `getting-started.md`: update the `pip install app` line.
- `reference.md`: after the package rename, update the `automodule` names. The docs build
  fails while they point at `app`.

## Claude settings

In `.claude/settings.json`, add `skillOverrides` to switch off installed plugin skills that
don't fit your stack, for example `{"go-review": "off"}`. Where two plugins cover one
domain, keep the more specific; keep universal skills on. Update any agent's `skills:`
frontmatter that names a skill you switched off.

## Dependabot labels

Dependabot creates its own `dependencies` and ecosystem labels, but adds `major`, `minor` or
`patch` to its PRs only if those labels exist. Create them:

```bash
gh label create major --color B60205 --description "Major version update" --force
gh label create minor --color FBCA04 --description "Minor version update" --force
gh label create patch --color 0E8A16 --description "Patch version update" --force
```
