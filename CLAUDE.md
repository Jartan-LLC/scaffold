# Project Name

<!-- ONE LINE: what this project is, primary language/framework, deployment target -->

## Rules

### Always

- Read README.md and relevant docs before modifying unfamiliar code
- Run Verify commands before declaring work done
- Update docs and skills alongside code changes
- Run the `doc-reviewer` pass on any docs change before it reaches review (see Docs)
- Write Google-style docstrings for public modules, classes, and functions (enforced by ruff `D`) and full type annotations (enforced by pyright `strict`)
- Keep `>>>` examples in those docstrings runnable — `make test` executes every one under `src/`, so a published example can't drift from its code
  <!-- Not a Python project? Swap these two rules for your stack's docstring/typing conventions. -->
- Write plans to `.claude/workspace/` in the project root for non-trivial changes

### Anti-patterns

- Don't wrap things the underlying library already expresses clearly
- Don't speculate about fixes — investigate first, then propose
- Don't hardcode derived counts in comments — they drift silently
- Don't put paragraph-length inline comments in CI/config files

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

## Docs

The prose bar is `praxis:docs-patterns`; the review pass is praxis's `doc-reviewer`
agent. Both ship in the `grimoire` marketplace `.claude/settings.json` declares.
CI gates structure and links — nothing gates whether a doc earns its length.

Plugins resolve from the session's project root, so an agent rooted above this
directory loads no plugins and reads the two files from a checkout instead, at the
ref `.claude/settings.json` pins:

```bash
git clone --depth 1 --branch <ref> https://github.com/Jartan-LLC/grimoire.git \
  .claude/workspace/grimoire
# plugins/praxis/skills/docs-patterns/SKILL.md — the bar
# plugins/praxis/agents/doc-reviewer.md — the pass
```

## Verify

Run `make check` before declaring work done — it runs every CI check (lint,
typecheck, test, build, audit, docs):

```bash
make check
```

Individual targets (`make lint`, `make test`, `make docs`, …) speed up the inner
loop; `make help` lists them.

<!-- Not a Python project? Point the Makefile targets at your stack's lint/format/typecheck/test equivalents. -->
