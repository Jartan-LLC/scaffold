# Project Name

<!-- ONE LINE: what this project is, primary language/framework, deployment target -->

## Rules

The project rules live in `GUARDRAILS.md`, ranked by how firmly each holds; this import
loads them into every session:

@GUARDRAILS.md

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
