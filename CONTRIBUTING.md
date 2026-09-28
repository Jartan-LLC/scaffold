# Contributing

## Setup

```bash
uv venv        # skip in the devcontainer or with an environment already active
make install
```

`make install` installs the project's dependencies and wires the pre-commit hook; rerun it
after dependencies change. Make targets find the environment themselves; activate `.venv`
only if you want `pytest` directly on your shell's PATH.

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
`make lint` runs the [pre-commit](https://pre-commit.com/) hooks; some need
Docker (actionlint, lychee) and Node (markdownlint) — the devcontainer has both.

## Verify before opening a PR

```bash
make check
```

Runs the same checks CI does (CI also runs the tests on each supported Python); all must
pass before merge.

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- User-facing changes go in `CHANGELOG.md` under `## [Unreleased]`.
- `>>>` examples in docstrings run as tests, so keep them executable and their
  expected output exact — the suite fails when one drifts from the code.
- Report security issues privately via [SECURITY.md](.github/SECURITY.md), not a public issue.
