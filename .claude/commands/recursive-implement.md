---
description: Build a project using recursive multi-agent development with TDD
argument-hint: Project description, issue number, or plan file path
---

# Recursive Implement

Build a project (or feature) using waves of parallel nested subagents with TDD at every level.

## Process

### 1. Launch the Orchestrator

Spawn a single agent with `subagent_type: "recursive-orchestrator"` passing `$ARGUMENTS` as the prompt content. The orchestrator handles everything: planning (via `recursive-planner`), wave execution, review-fix cycles, and documentation.

If `$ARGUMENTS` is an issue number, fetch the issue body first and include it in the prompt.

### 2. Report Results

Relay the orchestrator's final report to the user.

## Failure Recovery

If the orchestrator reports a failure it couldn't resolve:
- Present the failure context to the user
- Options: fix manually and re-run, adjust the plan, or abort
- The wave plan file in `.claude/workspace/` can be edited and passed back as a plan file path to retry
