# Contributing

## Setup

```bash
uv venv        # not in the devcontainer, nor with an environment already active
make install
```

`make install` installs the package with its dev extras and every other git-tracked
`pyproject.toml`, `requirements.txt` and `package.json`, then wires the pre-commit hook.
Every `make` target uses the first of these Python environments:

1. this checkout's `./.venv`;
2. the active environment (`VIRTUAL_ENV`);
3. in the devcontainer's own checkout, the system Python, because the container sets
   `UV_SYSTEM_PYTHON` (`1` or `true`);
4. none: installing targets stop and ask you to run `uv venv` or activate one.

The Makefile tells uv which one, since uv alone ignores `.venv` under `UV_SYSTEM_PYTHON`
and prefers `VIRTUAL_ENV`. A linked git worktree never falls through to the system
Python, which holds the main checkout's install: give it its own `uv venv`. You never
need to activate `.venv`; activate anyway (`source .venv/bin/activate`) if you want
`pytest` directly on your shell's PATH.

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
`make lint` runs the [pre-commit](https://pre-commit.com/) hooks; some need
Docker (actionlint, lychee) and Node (markdownlint) — the devcontainer has both.

## Verify before opening a PR

```bash
make check
```

Runs the same checks CI does (in the environment Setup describes — CI also sweeps the
3.12/3.13 matrix); all must pass before merge.

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- User-facing changes go in `CHANGELOG.md` under `## [Unreleased]`.
- `>>>` examples in docstrings run as tests, so keep them executable and their
  expected output exact — the suite fails when one drifts from the code.
- Report security issues privately via [SECURITY.md](.github/SECURITY.md), not a public issue.
