# Setting up the template

Work through the sections below in order. `/onboard` in Claude Code works through the page
for you. Finish deletes this page;
[`scaffold.md`](scaffold.md) covers what stays useful afterwards.

## Decide

Settle these first: the steps below take their values from the answers. Where an answer
needs no procedure, its item says what to do with it.

- [ ] Project name and one-line description; for Python, the distribution and import names,
      and whether it has a command-line interface
- [ ] GitHub org and repo, and the code owners
- [ ] Stack: language and framework, deployment target, and the lint, test and build commands
      if it isn't Python
- [ ] License, and the author and copyright holder ([License](#license))
- [ ] Contacts for conduct reports and security reports, one address or two. Both are
      published, so give addresses you are willing to publish
- [ ] Which enchantments Features to keep ([Features](#features))
- [ ] Publishing targets: the PyPI package, the container image, the docs site.
      [Publishing](scaffold.md#publishing) says what each needs and what to delete for each
      you drop
- [ ] Whether to keep `Dockerfile` (its marker says what goes with it),
      `.github/workflows/scorecard.yml` (an OpenSSF score; it skips on private repos) and
      `.github/workflows/external-link-check.yml` (a weekly check for broken external links).
      Delete each workflow you don't keep
- [ ] Optionally: version corrections for `AGENTS.md`, and the supported versions and
      response targets for `.github/SECURITY.md`

## Procedures

Run these in order. Each runs on the files the one before it left.

1. [ ] [Features](#features)
2. [ ] [Rename the Python package](#python-package), or [tear down Python](#not-a-python-project)
3. [ ] [Stack](#stack)
4. [ ] [License](#license)
5. [ ] Tests (Python): add tests of your code. `tests/test_smoke.py` only checks that the
       CLI stub runs. Replace it, unless the project has no CLI: then the `__main__.py`
       marker deletes it

### Features

For each [enchantments](https://github.com/Jartan-LLC/enchantments) Feature you decline:

1. While it is still declared, run the in-clone steps of the Removal section on its page, if
   it has one ([the Features list](https://github.com/Jartan-LLC/enchantments#features) links
   each page).
2. Remove its entry from `devcontainer.json` and its key from `devcontainer-lock.json`.
3. Do the rest of its Removal steps in their order, such as removing the container and then a
   volume, and rebuild.

Also:

- Declining `claude-code` means declining `codebase-memory-mcp` too, if you added it, and
  declining `liza` means declining `liza-toolchain`.
- To keep a code graph without `liza-toolchain`, declare `codebase-memory-mcp` in its place.
- A Feature in your VS Code `dev.containers.defaultFeatures` comes back on rebuild, so
  declining it here applies only to contributors who don't set it. Declare `liza` and
  `liza-toolchain` both in `devcontainer.json` or both only in `defaultFeatures`
  ([liza-toolchain](https://github.com/Jartan-LLC/enchantments/blob/main/src/liza-toolchain/README.md)).

### Python package

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

### Not a Python project

This deletes the docs site, and with it some markers, so it runs before [Markers](#markers).
Keep `docs/scaffold.md`, which reads fine on GitHub without Sphinx, and this page, which
Finish deletes.

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

### Stack

- `devcontainer.json`: add or remove Features and extensions for your stack.
- `post-start.sh`: add commands to run on each container start. The Docker socket fix and
  Codespaces environment overrides are already there.
- The `Makefile`'s `install` target: add your stack's install (for example
  `go mod download`). It runs on a bare host and from `post-create.sh`.
- `.gitignore` and `.editorconfig`: add your stack's patterns and rules.
- `.github/workflows/ci.yml` and `.github/dependabot.yml`: prune them to your stack
  ([CI](scaffold.md#ci)).

### License

Keep `LICENSE` (MIT) with your own year and name, or replace it with one of the `LICENSE.*`
templates, filling in `[year]` and `[fullname]`: `LICENSE.proprietary` is all rights
reserved, for private or closed-source work. A license not among the templates replaces
`LICENSE` the same way. Then delete the `LICENSE.*` files.

## Markers

Every line the template ships is true both in the template and in a project made from it,
carries a `TODO(/onboard): <what to do>` marker, is changed by a procedure above, or sits in
a file onboarding deletes or replaces (this page, `.claude/commands/onboard.md`, `README.md`
and the license files). Text that waits on project code, such as the `ci.yml` jobs to
uncomment once you add their inputs, carries no marker: it stays true after onboarding.

1. List the markers:

   ```bash
   git grep -n 'TODO(/onboard)'
   ```

2. Do what each marker says, then delete the marker. Decide gives every value a marker
   needs except the optional ones in `.github/SECURITY.md`. With no answer for the supported
   versions or the response targets, rewrite that marked line to state only the default it
   gives (for the supported versions, `Report against the latest release.`), and delete the
   comment with the example table. Never fill in a value nobody gave.
3. Run the grep again. It should print only this page, the marker on its `docs/index.md`
   entry, which Finish deletes, and `.scaffold-sync`, which the next section fills or, in a
   fork, deletes.

## Record the sync point

`.scaffold-sync` records the scaffold commit this repository has caught up to, so you can
pull in later template changes ([Syncing template updates](scaffold.md#syncing-template-updates)).
It ships holding a marker, because a file can't name the commit that contains it.

If you created the repository with *Use this template*, its first commit is an exact copy of
one scaffold commit's tree. Write that commit to the file:

```bash
git remote add upstream https://github.com/Jartan-LLC/scaffold.git
git fetch upstream
tree=$(git rev-parse "$(git rev-list --max-parents=0 HEAD)^{tree}")
sha=$(git log --format='%H %T' upstream/main | awk -v t="$tree" '$2 == t {print $1; exit}')
test -n "$sha" && echo "$sha" > .scaffold-sync
```

If `test -n` fails, the file keeps its marker. In a shallow clone, run
`git fetch --unshallow` and try again; otherwise no scaffold commit has the first commit's
tree, so write the scaffold commit you started from into the file by hand. The `upstream`
remote stays for [syncing](scaffold.md#syncing-template-updates).

If you forked scaffold instead, delete `.scaffold-sync`: the history is shared, so
`git merge upstream/main` brings in later changes.

## GitHub settings

- [ ] Private vulnerability reporting (Settings > Security): until it is on, the advisory
      form `SECURITY.md` links to does not exist
- [ ] The `major`/`minor`/`patch` labels Dependabot adds to its PRs ([details](#dependabot-labels))
- [ ] A branch ruleset for `main`: require PR reviews, require the `check` status to pass,
      block force pushes
- [ ] CodeQL default setup (Settings > Security > Code scanning)
- [ ] Secret scanning with push protection (Settings > Security > Secret Protection)
- [ ] Auto-merge (Settings > General > Allow auto-merge): Dependabot minor and patch PRs
      merge after CI passes
- [ ] Discussions (Settings > General > Features): the issue template config links to it
- [ ] For each publishing target you kept, its `pypi` or `ghcr` environment with required
      reviewers ([Publishing](scaffold.md#publishing))

### Dependabot labels

Dependabot creates its own `dependencies` and ecosystem labels, but adds `major`, `minor` or
`patch` to its PRs only if those labels exist. Create them:

```bash
gh label create major --color B60205 --description "Major version update" --force
gh label create minor --color FBCA04 --description "Minor version update" --force
gh label create patch --color 0E8A16 --description "Patch version update" --force
```

## Finish

1. [ ] Replace `README.md` with your own, carrying over its badges adjusted for your repo
       ([details](#readme-badges)).
2. [ ] Delete this page, its entry in `docs/index.md` with the marker above it (unless
       tearing down Python deleted `docs/index.md`), and `.claude/commands/onboard.md`.
3. [ ] Run `git grep -n 'TODO(/onboard)'`. It must print nothing.
4. [ ] Run `make check`.

### README badges

Copy the badge lines from the top of the template README into yours, then:

- Replace `Jartan-LLC/scaffold` with your org and repo in each badge.
- License badge: replace `MIT` in `license-MIT-blue` with your license. shields.io splits the
  badge text on `-`, so write each `-` in the name as `--` (`license-Apache--2.0-blue`).
- Delete the OpenSSF Scorecard badge if you deleted `scorecard.yml` or the repo is private.
