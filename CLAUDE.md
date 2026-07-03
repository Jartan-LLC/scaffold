# Project Name

<!-- ONE LINE: what this project is, primary language/framework, deployment target -->

## Rules

### Always
- Read README.md and relevant docs before modifying unfamiliar code
- Run Verify commands before declaring work done
- Update docs and skills alongside code changes
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

Run before declaring work done — these mirror `.github/workflows/ci.yml`:

```bash
ruff check .           # lint
ruff format --check .  # formatting
codespell              # spelling
pyright                # type check
pytest                 # tests
```

Also `shellcheck` any changed `*.sh`. Packaging checks (`python -m build`, `twine check`)
run in CI on `v*` tags. If this isn't a Python project, replace the commands above with
your stack's lint/format/typecheck/test equivalents.
