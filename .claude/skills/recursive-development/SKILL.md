---
name: recursive-development
description: Patterns for decomposing plans into waves of parallel nested subagents with unlimited depth, TDD at every level, and scope-based ownership.
when_to_use: Transforming implementation plans into recursive subagent wave structures, or when working with nested subagent orchestration.
user-invocable: true
---

# Recursive Development with Nested Subagents

Decompose work into waves of parallel nested subagents. Works for both greenfield projects and adding features to existing codebases. Each wave completes before the next starts. Within a wave, independent modules run in parallel. Each module can recursively spawn sub-agents — there is no depth limit.

For existing projects, Wave 0 extends rather than creates — reading established patterns (error classes, logging, naming, DI) and conforming to them. The plan's "Existing Patterns" section captures these constraints so all downstream agents follow them.

## Nesting Depth

There is no hard limit on nesting depth. Agents can spawn agents that spawn agents indefinitely. The practical limit is the work itself — at some point a concern is atomic and further splitting adds overhead with no benefit.

**Default to nesting.** Each nested agent has a smaller context window than its parent — it only sees its contract and owned files, not the full plan. This makes nested agents faster and cheaper per-agent than doing the same work in a single large context. A flat agent juggling 7 files costs more tokens than 3 focused agents each handling 2-3 files.

Nest whenever a module has 2+ independently testable concerns. Stop when the work is a single concern in a single file.

### Typical roles by level

These are common patterns, not prescribed layers. Skip levels that don't apply.

| Role | Scope | Spawns when... |
|------|-------|----------------|
| **Orchestrator** | Shared files + wave sequencing | Always — dispatches waves |
| **Module agent** | Directory scope | Module has 2+ testable concerns |
| **Component agent** | File set scope | Component has separable sub-concerns |
| **Leaf agent** | Single file pair | Never — implements and tests directly |

### Model selection by level

| Level | Role | Recommended model |
|-------|------|-------------------|
| 1-2 | Orchestrator, wave coordinator | **opus** — architectural judgment, decomposition decisions, subagent prompt design |
| 3 | Module implementer | **sonnet** — well-specified contract, focused scope, good TDD |
| 4-5 | Component builder, leaf | **sonnet** — single file, mechanical, clear contract |

The orchestrator benefits most from a stronger model — it decides decomposition, writes contracts, and detects file ownership conflicts. That's judgment work. Lower levels are well-constrained by contracts and benefit less from a stronger model.

## Core Principles

### 1. Scope-Based Ownership

**No two parallel subagents may touch the same file.** This is the hardest constraint and the one most likely to cause failures if violated.

Ownership scope adapts to the level of nesting:

| Level | Typical scope | Example |
|-------|--------------|---------|
| Wave | Directory | `src/config/` |
| Module | Directory or file set | `src/config/` or `['src/config/parser.ts', 'src/config/parser.test.ts']` |
| Sub-component | File set | `['src/config/validator.ts', 'src/config/validator.test.ts']` |
| Leaf | Single file pair | `['src/config/parser.ts', 'src/config/parser.test.ts']` |

**Directory scope** means the agent may create any files under that directory. Use at the wave/module level when the agent decides its own file structure.

**File set scope** means the agent may only touch the listed files. Use when a parent splits work within a shared directory — two sub-agents can work in the same directory as long as their file sets don't overlap.

Shared files (e.g. `src/types.ts`, `src/index.ts`) are owned by whichever wave creates them. Later waves may read but not modify them. If a later agent needs a new shared type, it reports the need upward — the orchestrator adds it before the next wave.

Before dispatching parallel agents:
- Assign each agent a scope (directory or file set)
- Verify zero overlap between parallel agents' scopes
- Shared files are created by the **parent** before dispatching children

### 2. TDD at Every Level

Each level follows the same cycle:
1. **Parent defines contracts** — types, interfaces, function signatures
2. **Agent writes tests first** — against the contracts from parent
3. **Agent implements** — minimal code to pass tests
4. **Agent verifies** — runs tests, reports pass/fail up

At levels 3+, the agent **should** delegate steps 2-4 to child agents when the module has multiple independently testable concerns. The parent defines contracts; children implement and test them. This keeps each agent's context small and focused.

### 3. Context Flows Down, Status Flows Up

**Down (parent → child):**
- Interface contracts (types, signatures, expected behavior)
- Ownership scope (directory path or explicit file set)
- Dependency information (what other modules provide, as interfaces only)

**Up (child → parent):**
- Pass/fail status
- Any interface changes needed (parent decides whether to accept)
- Files created/modified (for verification against ownership)

**Never pass down:** Full codebase context, other modules' implementation details, the entire plan.
**Never pass up:** Internal implementation decisions, intermediate debugging steps.

### 4. Wave Sequencing

Waves execute sequentially. Wave N+1 starts only after Wave N completes and all its tests pass.

Typical wave structure:
- **Wave 0**: Shared types, interfaces, contracts (no implementation)
- **Wave 1**: Foundation modules with no internal dependencies
- **Wave 2**: Modules that depend on Wave 1 outputs
- **Wave N**: Integration, wiring, top-level entry points
- **Wave N+1**: Cross-module integration tests

### 5. Error Handling Across Levels

When a child agent fails:
1. **Report up** with the failure context (which test, what error)
2. **Parent decides**: retry (same agent, fresh context), restructure (split differently), or escalate (report to its parent)
3. **Max 2 retries** at any level before escalating
4. **Never silently swallow failures** — every failure must reach the orchestrator

## Transforming a Plan into Waves

When in plan mode, restructure an existing plan using this process:

### Step 1: Extract Modules
Identify independent units of work. A module is independent if it can be tested without the implementation (only the interfaces) of other modules.

### Step 2: Map Dependencies
Draw the dependency graph between modules. Dependencies flow through **interfaces only** — never through implementation details.

### Step 3: Assign Waves
- Modules with no dependencies → Wave 1 (Wave 0 is always shared types)
- Modules depending only on Wave 1 → Wave 2
- Continue until all modules are assigned

### Step 4: Decompose Modules
Module agents decide their own internal decomposition. The split criteria is **algorithmic independence**, not testability:

- Does the module contain distinct algorithms or domains? → Split into children
- Are the sub-parts steps in a single operation? → Keep together

Examples of good splits:
- Cycle detection + topological sort (different graph algorithms)
- Formatting functions + event dispatch (pure vs stateful, different domains)
- Runtime validation + schema definition (when both have substantial logic)

Examples of bad splits:
- File discovery + file reading (one operation: "load a config")
- A parser that just wraps a validator (no distinct logic)
- Output capture separate from execution (capturing is part of executing)

The goal is a file structure that would look natural in a human-maintained codebase. Err toward splitting when genuinely distinct algorithms are involved, but don't create files just to have something to delegate.

### Step 5: Assign Ownership Scopes
For each wave, assign scopes to parallel agents. At wave level, directories are typical. Resolve conflicts by:
1. Moving shared files to an earlier wave (orchestrator owns them)
2. Narrowing from directory scope to file set scope when two agents need the same directory
3. Splitting a file into per-agent pieces with a later merge wave

### Step 6: Define Contracts
For each parent-child boundary, write explicit contracts:
- TypeScript: interface/type definitions
- Python: Protocol classes or typed function signatures
- Other: whatever the language's equivalent is

## Wave Plan Format

Structure the transformed plan as:

```
## Wave 0: Contracts
- Scope: [shared files the orchestrator owns]
- Defines: [interfaces, types, shared constants]

## Wave 1: [name]
### Module A (scope: src/foo/)
- Contract: [what it implements]

### Module B (scope: src/bar/)
- Contract: [what it implements]

## Wave 2: [name]
### Module C (scope: src/baz/)
- Depends on: Module A, Module B (interfaces only)

## Wave N: Integration
### Wiring (scope: [src/index.ts, src/cli.ts])
### E2E Tests (scope: [src/__tests__/, fixtures/])
```

## Style Consistency via Agent Type

Parallel agents with different style tendencies produce inconsistent code (semicolons vs no-semicolons, different comment styles, different error message formats). Solve this with a shared agent definition.

Use `subagent_type: "recursive-implementer"` for all module agents. This agent has:
- A style contract (formatting, naming, module patterns, error messages, comments)
- TDD process and nesting instructions
- File ownership enforcement

Children spawned by module agents should also use `recursive-implementer` — the style contract propagates down the tree. Keep subagent prompts minimal: contract, ownership scope, dependency interfaces. The agent definition carries everything else.

## Token Economics

Nesting is a **token efficiency strategy**, not a cost multiplier. Each nested agent carries less context than its parent — it only sees its contract and owned files. Compare:

- **Flat**: 1 agent with full plan + all module code in context → large context, expensive per-token
- **Nested**: N agents each with 1 contract + 1-2 files in context → small context, cheap per-agent

The total token count across all agents may be similar or lower than a single agent doing everything, because each agent's context is dramatically smaller. The wall-clock time is also lower because nested agents within a wave run in parallel.

Guidelines:
- Pass minimal context to every agent. They need their contract and file ownership — nothing else.
- Leaf agents are cheap by design. Don't hesitate to spawn them.
- More agents with less context each > fewer agents with large context each.
- The orchestrator (level 1-2) is the most expensive agent because it holds the global plan. Keep it thin — it dispatches, it doesn't implement.

## Contract Richness

Wave 0 contracts determine the ceiling of what the entire system can do. Thin contracts produce thin implementations. Contracts should be **rich, flexible, and robust**:

### Design for completeness
- Enumerate all operations the module should support, not just the common ones. If an aggregation engine should support count, sum, avg, min, max, and percentiles — define all of them in the contract, not just count and avg.
- Use enums or literal unions for closed sets of operations/formats/modes. This makes the contract self-documenting and prevents string-typing drift.
- Define error types alongside success types. A parser that can fail on malformed input should yield `Record | ParseError`, not raise exceptions that crash the pipeline.
- Define a custom exception hierarchy — a project-level base exception with specific subtypes for each failure domain (parse errors, invalid filter expressions, aggregation errors, I/O errors). This lets callers catch specific failures.

### Design for flexibility
- Interfaces that accept multiple items (`list[AggregationSpec]`) are more useful than single-item interfaces. One pass over the data computing 5 aggregations beats 5 passes computing 1 each.
- Injectable I/O (write functions, output streams) enables testing without mocking. Accept callables or protocols, not concrete implementations.
- Use union return types (`Record | ParseError`) over exceptions for expected failure modes. Reserve exceptions for truly unexpected errors.

### Design for modularity
- Protocol classes (Python) or function signatures (TypeScript) for DI — not concrete class dependencies.
- Factory functions or registries for selecting implementations at runtime (`get_parser("jsonl")`, `get_formatter(OutputFormat.TABLE)`).
- Structured return types that wrap results (e.g. `RunResult` with results + success + duration) rather than bare values.

### Contracts are types only
The shared contracts file should contain **only type definitions**: protocols, dataclasses, enums, type aliases, and constants. It should NOT contain callable stubs (`def get_parser(...): raise NotImplementedError`). Factory functions, parsers, and other implementable logic belong in their implementing modules. The contracts file defines the shapes; modules define the behavior.

## Agent Constraints

These constraints apply to ALL agents in the recursive tree, not just the orchestrator:

- **No worktree isolation.** Never use `isolation: "worktree"` when spawning subagents. Worktree agents work in a copy and their files get discarded on cleanup. All agents must work directly in the main working directory.
- **No background agents.** Never use `run_in_background: true` when spawning subagents. Background dispatch triggers worktree isolation. Use foreground Agent calls — send all parallel agents in a single message for concurrency.
- **Fix delegation.** When a reviewer reports findings, simple fixes (unused import, missing return) can be done directly. Fixes that touch logic (bug fix, structural merge, new edge case handling) should be delegated to a `recursive-implementer` agent scoped to the affected files with the findings in the prompt.

## Quality Patterns

Patterns that consistently produce better code across recursive waves:

- **Process group kills**: Executors that spawn child processes should use `detached: true` + `process.kill(-pid, signal)` to kill the entire process tree on timeout.
- **Double-resolve guards**: Async code wrapping callbacks should use a `settle()` guard to prevent resolving twice.
- **System boundary validation**: Modules accepting external input should validate at the boundary. Don't trust parsed input matches the expected shape.
- **Graceful degradation**: Parsers should yield errors for bad lines and continue, not crash the pipeline. Data processors should tolerate malformed input.
- **Content-based detection**: When auto-detecting formats, inspect content (try parsing first lines) rather than relying solely on file extensions.
- **Logging**: Use the language's logging framework (`logging` in Python, `console`/`pino` in Node, `log` in Rust). Library code uses named loggers — never writes to stderr/stdout directly. Entry points (CLI, main) configure log level and format. Callers control verbosity, not libraries.
- **Error handling**: Use union return types (`Result | Error`) for expected failure modes that callers should handle. Reserve exceptions for truly unexpected errors (programming bugs, system failures). Error messages should include enough context for the user to fix the problem — the field name, the bad value, what was expected.
- **Custom error hierarchy**: Define a project-level base exception and specific subtypes for distinct failure modes (parse errors, filter expression errors, aggregation errors, I/O errors). Callers should be able to catch specific failures without catching everything. This should be part of Wave 0 contracts.
- **Path abstractions**: Use the language's path library (`pathlib` in Python, `path` in Node, `std::path` in Rust). Never concatenate path strings. Never use hardcoded absolute paths in source or tests — use relative paths from `__file__`, project root, or test fixtures.
- **Runtime versioning**: Expose the project version programmatically (e.g. `__version__` attribute, `package.json` version field). CLI modules should support a `--version` flag. Don't rely solely on build config for version access.
- **Test coverage**: Configure coverage tooling with the project's test framework. Set a minimum threshold so gaps are visible in CI. Coverage config belongs in the project config file alongside test config.

## Anti-Patterns

- **God orchestrator**: Orchestrator that micromanages every file. It should only manage waves and contracts.
- **Context dumping**: Passing the entire plan to every child. Each child gets only its contract and file list.
- **Shared file optimism**: Assuming parallel agents won't conflict. They will. Verify ownership.
- **Test-after at depth**: Skipping TDD because "it's just a leaf node." Every level writes tests first.
- **Unbounded retry**: Retrying failed agents indefinitely. Cap at 2, then escalate.
- **Artificial splitting**: Creating sub-agent files just to have something to delegate. If the sub-parts are steps in one operation (find file → read file → parse content), keep them together. Split only for genuinely distinct algorithms or domains.
- **Over-specified plans**: Plans that prescribe internal file structure, test cases, or sub-component names. The agents discover these through TDD — the plan defines boundaries and responsibilities only.
- **Hardcoded absolute paths**: Using absolute paths in source or tests (e.g. `/workspaces/scaffold/tests/fixtures`). These break when the project is cloned elsewhere. Use paths relative to `__file__`, project root, or test discovery.
