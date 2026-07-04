# Project Name

<!-- ONE LINE: what this project is, primary language/framework, deployment target -->

## Rules

### Always

- Read README.md and relevant docs before modifying unfamiliar code
- Run Verify commands before declaring work done
- Update docs and skills alongside code changes
- Write Google-style docstrings for public modules, classes, and functions (enforced by ruff `D`) and full type annotations (enforced by pyright `strict`)
  <!-- Not a Python project? Swap this rule for your stack's docstring/typing conventions. -->
- Write plans to `.claude/workspace/` in the project root for non-trivial changes

### Anti-patterns

- Don't wrap things the underlying library already expresses clearly
- Don't speculate about fixes — investigate first, then propose
- Don't hardcode derived counts in comments — they drift silently

### Ask first

- Changing public API signatures or database schemas
- Deleting files or removing features

### Never

- Commit or push unless explicitly asked or instructed by a command
- Add dependencies without stating the reason
- Put secrets or credentials in tracked files

## Corrections

<!-- Version mismatches are the most common — fill these in early.
"We use Pydantic v2 field_validator, not v1 validator."
"Next.js 15 uses async cookies() — not the sync API from v14." -->

## Skills

<!-- Add project-specific skills and conventions here as they develop. -->

## Verify

Run `make check` before declaring work done — it runs every CI check (lint,
typecheck, test, build, audit, docs):

```bash
make check
```

Individual targets (`make lint`, `make test`, `make docs`, …) speed up the inner
loop; `make help` lists them.

<!-- Not a Python project? Point the Makefile targets at your stack's lint/format/typecheck/test equivalents. -->
