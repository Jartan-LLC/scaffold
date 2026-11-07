# Setting up the template

The setup checklist, then the details for each item that needs more than a line. `/onboard`
in Claude Code works through it for you. Delete this page (and its entry in `index.md`) at
Cleanup; [`scaffold.md`](scaffold.md) covers what stays useful afterwards.

## Checklist

### Required

- [ ] Fill in `AGENTS.md` and `GUARDRAILS.md` ([details](#project-instructions))
- [ ] Adapt the devcontainer and the `Makefile`'s `install` target to your stack ([details](#devcontainer))
- [ ] Keep or decline each enchantments Feature ([details](#devcontainer))
- [ ] Add your stack's patterns to `.gitignore` and rules to `.editorconfig`
- [ ] Enable private vulnerability reporting (Settings > Security): until it is on, the advisory form `SECURITY.md` links to does not exist
- [ ] Rename the Python package ([details](#python-package)), or tear down Python ([details](#not-a-python-project))
- [ ] Replace `tests/test_smoke.py` with real tests
- [ ] Prune `.github/workflows/ci.yml` and `.github/dependabot.yml` to your stack ([details](scaffold.md#ci))
- [ ] Set your license: keep `LICENSE` (MIT) with your own year and name, or replace it with one of the `LICENSE.*` templates (filling in `[year]` and `[fullname]`), then delete the `LICENSE.*` files
- [ ] Resolve the `TODO(/onboard)` markers ([details](#markers))

### Recommended

- [ ] Set up publishing: package, image, docs site, with required reviewers on the `pypi` and `ghcr` environments ([details](scaffold.md#publishing))
- [ ] Create the `major`/`minor`/`patch` labels Dependabot adds to its PRs ([details](#dependabot-labels))
- [ ] Enable GitHub Discussions (Settings > General > Features) — issue template config links to it
- [ ] Enable CodeQL default setup (Settings > Security > Code scanning)
- [ ] Delete `.github/workflows/scorecard.yml` if you don't want an OpenSSF score (it skips on private repos)
- [ ] Delete `.github/workflows/external-link-check.yml` if you don't want the weekly check for broken external links
- [ ] Enable secret scanning with push protection (Settings > Security > Secret Protection)
- [ ] Configure branch ruleset for `main` — require PR reviews, require the `check` status to pass, block force pushes
- [ ] Enable auto-merge (Settings > General > Allow auto-merge) — Dependabot minor/patch PRs auto-merge after CI passes

### Cleanup

- [ ] Replace `README.md` with your own, carrying over its badges adjusted for your repo ([details](#readme-badges))
- [ ] Delete this page and its entry in `docs/index.md`
- [ ] Delete `.claude/commands/onboard.md`

## Project instructions

- `AGENTS.md`: replace the `# Project Name` heading and the `<!-- ONE LINE: … -->` comment
  under it; add version-specific overrides for your stack under Corrections; add skills and
  conventions under Skills as they emerge. If your verify command is not `make check`,
  update the Verify section.
- `GUARDRAILS.md`: add project rules as they emerge, at the tier each must hold.

## Devcontainer

- `devcontainer.json`: add or remove Features and extensions for your stack.
- For each [enchantments](https://github.com/Jartan-LLC/enchantments) Feature you decline, follow
  the Removal section on its page, if it has one
  ([the Features list](https://github.com/Jartan-LLC/enchantments#features) links each page);
  otherwise remove its entry from `devcontainer.json`. Either way, also remove its key
  from `devcontainer-lock.json`, then rebuild. Also:
  - Declining `claude-code` means declining `codebase-memory-mcp` too, if you added it, and
    declining `liza` means declining `liza-toolchain`.
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
   (or replace that stub), and the `Dockerfile` `CMD` hint. Also update `--cov=app` in
   `ci.yml`'s commented `integration-tests` job.
5. Resolve the markers in `docs/getting-started.md` and `docs/reference.md`. The strict docs
   build fails while `reference.md` names `app`.

## Not a Python project

Do this before resolving the markers, after every other Required item: it deletes the docs
site, and with it some markers. Keep `docs/scaffold.md`, which reads fine on GitHub without
Sphinx, and this page, which Cleanup deletes.

1. Move `[tool.codespell]` from `pyproject.toml` to a `.codespellrc`.
2. Delete `pyproject.toml`, `src/`, `tests/`, everything in `docs/` but `scaffold.md` and this page,
   `.readthedocs.yaml.example`,
   `.github/workflows/pages.yml.example`, `.github/workflows/publish-pypi.yml` and
   `.github/workflows/dependency-audit.yml`. If not containerized, also `Dockerfile`,
   `.dockerignore`, `.github/workflows/publish-docker.yml` and the commented `docker` job in
   `.github/workflows/ci.yml`.
3. In `.pre-commit-config.yaml`, remove the `ruff-pre-commit` entry. Keep the other hooks.
4. In `.github/workflows/ci.yml`, remove the `python`, `test` and `docs` jobs and their
   `check` entries (`docs/scaffold.md`, CI), and the commented `integration-tests` job. In
   the `changes` job, remove the `python:` line under `outputs` and the `python=true` block,
   with its comment, in the `diff` step. `lint` stays.
5. Keep the `Makefile`: it is the verify entry point in every stack. Point its `lint`, `fix`,
   `typecheck`, `test` and `docs` targets at your stack's commands, and replace the Python
   lines in `check` (the `.[dev,docs]` install, `uv build`, `twine check`, `pip-audit`), so
   `make check` stays the one verify gate.
6. In `CONTRIBUTING.md`, rewrite the `make install` setup and the "Requires Python 3.12+ and
   uv" line for your stack.
7. Trim the Python parts of `docs/scaffold.md`.

## Markers

Every line the template ships is true both in the template and in a project made from it,
carries a `TODO(/onboard): <what to do>` marker, or sits in a file onboarding deletes or
replaces (this page, `.claude/commands/onboard.md`, `README.md` and the license files). Text
that waits on project code, such as the `ci.yml` jobs to uncomment once you add their inputs,
carries no marker: it stays true after onboarding.

1. List the markers:

   ```bash
   git grep -n 'TODO(/onboard)'
   ```

2. Do what each marker says, then delete the marker.
3. Run the grep again. Apart from this page and the marker on its `docs/index.md` entry,
   which Cleanup deletes, what it still prints is template text left in the project. Leave a
   marker only while you have no answer for it, such as the response targets in
   `.github/SECURITY.md`.

## Dependabot labels

Dependabot creates its own `dependencies` and ecosystem labels, but adds `major`, `minor` or
`patch` to its PRs only if those labels exist. Create them:

```bash
gh label create major --color B60205 --description "Major version update" --force
gh label create minor --color FBCA04 --description "Minor version update" --force
gh label create patch --color 0E8A16 --description "Patch version update" --force
```

## README badges

Copy the badge lines from the top of the template README into yours, then:

- Replace `Jartan-LLC/scaffold` with your org and repo in each badge.
- License badge: replace `MIT` in `license-MIT-blue` with your license. shields.io splits the
  badge text on `-`, so write each `-` in the name as `--` (`license-Apache--2.0-blue`).
- Delete the OpenSSF Scorecard badge if you deleted `scorecard.yml` or the repo is private.
