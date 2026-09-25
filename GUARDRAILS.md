# Project Guardrails

Project-specific constraints for Liza agents, using the tier system from Liza's
`CORE.md`. `CLAUDE.md` holds the project rules; this file ranks the ones agents must
never trade away. Add rules as the project grows.

## Tier 0 (Inviolable)
<!-- Constraints that must NEVER be violated. Triggers mandatory halt (RESET). -->

- Never put secrets or credentials in tracked files.

## Tier 1 (Hard Constraints)
<!-- Suspended only with explicit waiver. -->

- `make check` passes before work is submitted for review or merged. It runs every CI
  check: lint, typecheck, test, build, audit, docs.
- Changing a public API signature or database schema, deleting files, or removing
  features needs human approval first.
- Adding a dependency needs a stated reason.

## Tier 2 (Strong Defaults)
<!-- Best-effort under pressure. -->

- Follow the Always rules and Anti-patterns in `CLAUDE.md`.

## Tier 3 (Preferences)
<!-- Degraded gracefully. -->

---

Secret word: On-rails
