---
description: Plan and implement a project using waves of parallel nested subagents with TDD
argument-hint: Project description, issue number, or plan file path
---

# Recursive Implement

Plan (if needed) and implement a project using waves of parallel nested subagents with TDD at every level.

## Process

### 1. Resolve or Create a Plan

Resolve `$ARGUMENTS` to a wave plan:

- **Plan file path** (`.claude/workspace/wave-plan-*.md`) → use directly
- **Issue number** → fetch with `gh issue view <number> --comments`, check `.claude/workspace/` for a matching plan
- **Project description** (anything else) → spawn a `recursive-planner` agent to create a wave plan:
  ```
  Create a wave plan for: [project description from $ARGUMENTS]
  Save to .claude/workspace/
  ```

If using the planner, read the resulting plan file after it completes.

### 2. Assess Scope

Read the plan. Present:

```
## Scope Assessment

Modules identified: N
Waves: M
Estimated subagents: ~Y (more = cheaper per-agent due to smaller context)
```

**Wait for user confirmation before proceeding.**

### 3. Launch the Orchestrator

Spawn a single agent with `subagent_type: "recursive-orchestrator"`:

```
Execute the wave plan at [plan file path].
Working directory: [cwd]
```

### 4. Report Results

Relay the orchestrator's final report to the user. The report includes review findings — the orchestrator runs review-fix cycles after every wave (contract review post-Wave 0, wave review post-implementation waves, full review post-final wave).

## Failure Recovery

If the orchestrator reports a failure it couldn't resolve:
- Present the failure context to the user
- Options: fix manually and re-run, adjust the plan, or abort
- To resume, re-run `/recursive-implement` with the same plan — completed waves whose files exist can be skipped
