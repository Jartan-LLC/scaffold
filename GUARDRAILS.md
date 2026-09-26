# Project Guardrails

The project rules, ranked by how firmly each holds. `CLAUDE.md` imports this file, so
every Claude Code session loads it; Liza agents also enforce the tiers (Liza's `CORE.md`).

## Tier 0 (Inviolable)
<!-- Constraints that must NEVER be violated. Triggers mandatory halt (RESET). -->

- Never put secrets or credentials in tracked files.

## Tier 1 (Hard Constraints)
<!-- Suspended only with explicit waiver. -->

- Run the Verify command in `CLAUDE.md` before declaring work done or submitting it for
  review.
- Ask first before changing public API signatures or database schemas, deleting files, or
  removing features.
- Commit or push only when explicitly asked or instructed by a command. A Liza workflow
  step that commits counts as that instruction; none counts for pushing or opening pull
  requests, which stay human-initiated.
- State the reason for every dependency you add.

## Tier 2 (Strong Defaults)
<!-- Best-effort under pressure. -->

- Read README.md and relevant docs before modifying unfamiliar code.
- Update docs and skills alongside code changes.
- Run the `doc-reviewer` pass on any docs change before it reaches review (see Docs in
  `CLAUDE.md`).
- Write Google-style docstrings for public modules, classes, and functions (enforced by
  ruff `D`) and full type annotations (enforced by pyright `strict`).
- Keep `>>>` examples in those docstrings runnable — `make test` executes every one under
  `src/`, so a published example can't drift from its code.
  <!-- Not a Python project? Swap these two rules for your stack's docstring/typing conventions. -->
- Write plans to `.claude/workspace/` in the project root for non-trivial changes.
- Don't wrap things the underlying library already expresses clearly.
- Don't speculate about fixes — investigate first, then propose.
- Don't hardcode derived counts in comments — they drift silently.
- Don't put paragraph-length inline comments in CI/config files.

## Tier 3 (Preferences)
<!-- Degraded gracefully. -->

---

<!-- Liza agents recite this word to prove they read the file (see Liza's CORE.md). Keep it. -->
Secret word: On-rails
