# Contributing

## Setup

```bash
pip install -e '.[dev]'
```

Requires Python 3.12+.

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
