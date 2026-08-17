# Contributing

## Setup

```bash
make install
```

That creates `./.venv`, installs the package with its dev extras, and wires the
pre-commit hook. Every other `make` target runs out of that venv, so you never
need to activate it — activate anyway (`source .venv/bin/activate`) if you want
`pytest` and `ruff` directly on your shell's PATH.

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/),
which is this project's installer, resolver and build frontend in place of pip.
`make lint` runs the [pre-commit](https://pre-commit.com/) hooks; some need
Docker (actionlint, lychee) and Node (markdownlint) — the devcontainer has both.

## Verify before opening a PR

```bash
make check
```

Runs the same checks CI does (on your active interpreter — CI also sweeps the
3.12/3.13 matrix); all must pass before merge.

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- User-facing changes go in `CHANGELOG.md` under `## [Unreleased]`.
- `>>>` examples in docstrings run as tests, so keep them executable and their
  expected output exact — the suite fails when one drifts from the code.
- Report security issues privately via [SECURITY.md](.github/SECURITY.md), not a public issue.
