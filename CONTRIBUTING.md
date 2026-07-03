# Contributing

## Setup

```bash
pip install -e '.[dev]'
pre-commit install  # optional: run the lint hooks on every commit
```

Requires Python 3.12+. `make lint` runs the [pre-commit](https://pre-commit.com/)
hooks; some need Docker (actionlint) and Node (markdownlint) — the devcontainer has both.

## Verify before opening a PR

```bash
make check
```

Runs the same checks CI does; all must pass before merge.

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- User-facing changes go in `CHANGELOG.md` under `## [Unreleased]`.
- Report security issues privately via [SECURITY.md](.github/SECURITY.md), not a public issue.
