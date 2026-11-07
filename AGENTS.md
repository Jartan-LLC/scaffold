# Project Name

<!-- TODO(/onboard): replace the heading with the project's name, and this comment with one
line: what the project is, its primary language/framework and deployment target. -->

## Rules

The project rules live in `GUARDRAILS.md`, ranked by how firmly each holds. Claude Code
loads them through the import below; any other agent reads `GUARDRAILS.md` before
starting work.

@GUARDRAILS.md

## Corrections

<!-- Version mismatches are the most common — fill these in early. Kept when empty: the
heading is what prompts adding a correction. -->

<!-- TODO(/onboard): replace these examples with the project's own corrections, or delete them.
"We use Pydantic v2 field_validator, not v1 validator."
"Next.js 15 uses async cookies() — not the sync API from v14." -->

## Skills

<!-- Add project-specific skills and conventions here as they develop. Kept when empty: the
heading is what prompts adding one. -->

## Verify

Run `make check` before declaring work done — it runs CI's lint, typecheck, test, build
and docs checks, and the advisory dependency audit:

```bash
make check
```

Individual targets (`make lint`, `make test`, `make docs`, …) speed up the inner
loop; `make help` lists them.

<!-- TODO(/onboard): Not a Python project? Point the Makefile targets at your stack's lint/format/typecheck/test equivalents. -->
