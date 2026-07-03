# Contributing

## Setup

```bash
pip install -e '.[dev]'
```

Requires Python 3.12+.

## Verify before opening a PR

```bash
ruff check .
ruff format --check .
pyright
pytest
```

CI runs these same checks on every pull request (plus `shellcheck` and a
`python -m build` / `twine check` packaging check). All must pass before merge.

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- User-facing changes go in `CHANGELOG.md` under `## [Unreleased]`.
- Report security issues privately via [SECURITY.md](.github/SECURITY.md), not a public issue.
