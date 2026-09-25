<!-- Scaffold's AGENT_TOOLS.md for INSTALL_LIZA_TOOLS=false, adapted from Liza's
contracts/AGENT_TOOLS.md (Apache-2.0). Lists only tools this devcontainer provides. -->

# Agent Tools

Sub-contract for tool usage. Applies to all modes (Pairing, Liza, Subagent).
When a default tool is unavailable in the current session, fall through to the next option in the fallback chain.

## Decision Kernel

### Search and Navigation

Choose the highest-signal routing source before exploratory search: explicit user paths, changed-file lists, and section/symbol routers. `rg`/`git grep` are appropriate first moves for literals, filenames, commands, or config keys already known from the request; in Pairing mode, prefer the codebase-memory graph for structural questions (callers, call chains, architecture) over guessed broad keywords.

Phased repository search:

1. Orient: in Pairing mode, use the codebase-memory graph for architecture, symbols, and call paths; in any mode, native manifests and `rg --files` for layout.
2. Trace with `rg` for literals and references; for long docs/specs, use `rg -c "pattern" <paths>` to find candidates, then `rg -n '^#{1,6} ' <file>` and section-scoped reads.
3. Verify against source files before editing or claiming behavior.

Use bounded `rg` for exact text search and path discovery; use `git grep` for tracked/index/HEAD/history searches. Use direct, line-numbered reads (`nl -ba ... | sed -n ...`) for source-of-truth verification and edit discussion.

Before editing shared/exported symbols or unfamiliar control paths, establish impact with the codebase-memory graph (Pairing) or `rg` + direct reads (MAS). If that baseline suggests cross-module, lifecycle/state/review-flow, or high-risk impact, surface it through the normal Rule 7/approval checkpoint before editing. For uncommitted edits, verify impact with `git diff`, direct source reads, working-tree `rg`, and behavior tests; the graph index may lag uncommitted changes.

### Execution and Validation

1. Use `apply_patch` only for edits that touch one file, with a separate call per file. A shell `workdir` does not relocate a patch capability that exposes no `workdir`; resolve each target from the exact recorded absolute worktree, express it from the patch tool's actual root, and stop if the capability cannot reach it.
2. Use native manifests, lockfiles, and language-native commands for dependency, build, and validation evidence.
3. Validate edits with native build/test/lint/typecheck commands plus pre-commit on touched files.
4. Use WebFetch and WebSearch for docs and web lookup.
5. In MAS worktrees, do not use workspace-level or IDE/LSP-backed tools.

## Forbidden tools

Refer to Security Protocol

## Other authorized tools

Any non destructive tool by default.

## Mode Boundary

All modes: use source-of-truth tools for verification.
MAS worktree rule: Do not use workspace-level or IDE/LSP-backed tools in Liza multi-agent worktrees, even if the user has configured them for personal use. The codebase-memory graph is one: it indexes the root checkout, not your worktree. Use filesystem-truth tools tied to the current worktree instead: `rg`, `rg --files`, `find`, direct reads, native manifests, `git`, language-native commands, and `apply_patch`.
Pairing mode: user-personal workspace tools may exist, but they do not replace source-of-truth verification.

## Tool Routing

**Pre-Action Check:** Before file/search/web operations, use the default capability/tool from the table below. Table entries use capability labels, sometimes illustrated with concrete provider-surface examples; if the current session exposes the same capability under a different name, use the equivalent tool.
Default tools are mandatory unless the fallback condition applies or the tool is unavailable, errors, or is unsupported by the provider.
MCP server/tool names may be normalized differently across providers (for example `-` vs `_`). Treat concrete names below as examples; use the equivalent exposed name in the current session.
If a default MCP capability is referenced here but is not currently exposed in the tool list, use your tool-loading mechanism (e.g. `ToolSearch`, `tool_search`) to load that capability before falling back. Fallback is allowed only after the tool cannot be found/loaded, the loaded tool errors, or the result is insufficient.
Fallback tools are permitted ONLY when the fallback condition is met OR the default tool returns an error.

### Operations

| Operation | Default Tool | Fallback | Use Fallback When |
|-----------|---------------------------------------------------|----------|-------------------|
| Read multiple files | Native batch reads / parallel Read calls | shell reads | Need line-numbered source snippets or provider Read is unavailable |
| Single-file read (targeted) | `nl -ba <file> \| sed -n '<start>,<end>p'` | Read | Native read is lower-noise, already available, or line numbers are not needed |
| Directory exploration | `rg --files`, `find`, or `ls` | native tree/list capability | Need a structured tree and native shell output is insufficient |
| File discovery | `rg --files` | native filename search / `find` | `rg` unavailable |
| Project structure / modules | Pairing: codebase-memory architecture/graph search; MAS: native manifest reads + `rg --files` | native manifest reads + `rg --files` / `find` | Graph unavailable, not indexed, or in a MAS worktree |
| Dependency inspection | Native manifest reads + lockfiles | language-native dependency commands | Manifest/lockfile inspection is insufficient |
| Literal/regex code search | `rg` | — | — |
| Symbol discovery / lookup | Pairing: codebase-memory graph search + direct reads; MAS: `rg` + direct reads | `rg` + direct reads | Graph unavailable, insufficient, or in a MAS worktree |
| File edit | apply_patch | native edit tool, then a scripted exact-match edit | apply_patch is unavailable in this session |
| Web content | WebFetch | `curl` | Need raw HTML, pagination, or WebFetch is blocked |
| Current info / library docs | WebSearch, then WebFetch on the primary docs page | — | — |
| Code quality check (after edits) | Native build/test/lint/typecheck + direct reads | pre-commit touched files | No narrower native command exists |

### Codebase Exploration

| Question Type | Default Tool | Fallback | Use Fallback When |
|-------------------------------------------|--------------|----------|-------------------|
| Exact keyword ("TODO") | `rg` | — | — |
| Find files by name | Glob | `rg --files` / native filename search | Glob unavailable |
| Repo orientation and module impact | Pairing: codebase-memory architecture | `rg` + manifest reads + exact source reads | Graph unavailable/insufficient, or in a MAS worktree |
| Semantic repository search ("how does X work?") | Pairing: codebase-memory graph search | `rg` + exact reads | Graph unavailable/insufficient, or in a MAS worktree |
| Find references / callers | Pairing: codebase-memory call-path tracing | `rg` + direct reads | Graph unavailable/insufficient, or in a MAS worktree |
| Cross-file definitions | Pairing: codebase-memory code snippet lookup | `rg` + direct reads | Graph unavailable/insufficient, or in a MAS worktree |

### Precedence

- When two tools can answer the same question, prefer the one that minimizes context injection while preserving fidelity. Claude: apply this rule to your native tools — they are not the default when a lower-context alternative exists.
- **Local First**: Prefer local tools before remote tools when they answer the same question with equal fidelity.
- **Diff / review / exact file state**: `git` and native shell reads > cached/indexed summaries. Source-of-truth reads beat derived views.
- **Tracked or historical search**: Use `git grep` when the question is scoped to tracked files, the index, `HEAD`, or another Git revision. Use `rg` for working-tree search, including unstaged and untracked files.
- **File edits**: `apply_patch` may not be exposed. When it is absent, fall through to the session's native edit tool, then to a scripted edit. At every rung the edit must fail loudly on a missed
  anchor. Never edit with `sed`/`awk`: their substitutions report success while changing nothing. A scripted edit asserts its
  anchor first — read the file, `assert old in s`, then write.

### Tool Preferences

- **Markdown navigation**: For long Markdown specs, plans, and architecture docs, use `rg` only to identify candidate files or exact hits, then `rg -n '^#{1,6} ' <file>` to map headings and read the exact relevant section with `sed -n '<start>,<end>p' <file>`. Section-scoped reads are more reliable than guessed line windows around a hit.
- **`jq` for structured data**: Use `jq` for JSON. Prefer it over `Read` + manual parsing when extracting specific fields.

### Batching

Batch related operations within the same MCP server when possible.

### PR

PR title MUST follow Conventional Commits.

For non-trivial changes, synthesize the body from task context, specs/issues, existing behavior, diff, and validation evidence.

Prefer these sections when relevant:

- Summary
- Problem / Why
- Existing Context
- Approach
- Change Map
- Reviewer Focus
- Validation
- Risks / Rollback
- Not in Scope

Reference specs/issues in Summary or Problem when present.

For trivial changes, use a compact body, but still include why and validation.

### GitHub

Codex: DO NOT use `codex_apps.github`.

Use `gh` (GitHub CLI) for GitHub issues, PRs, releases, and GitHub API queries when repository context and authentication are available. Prefer `gh` over raw `curl` calls to GitHub APIs.

For any GitHub write that sends Markdown body text (issue/PR descriptions, comments, reviews, releases), DO write the intended Markdown to a temp file and pass that file to `gh` with `--body-file` or through a JSON payload file. Do not stream the body through stdin. After writing, read the body back with `gh api` and verify one or more unique exact phrases from the intended Markdown before claiming success.

DO NOT use `gh pr edit --body-file -`; it can produce empty or truncated bodies while reporting success.

DO NOT probe `gh pr edit` syntax by appending `--help` to a partially formed edit command. Run `gh pr edit --help` as a standalone command before constructing the state-changing command.

### Claude-specific operational notes

The rules below apply only to Claude sessions and should not be generalized to other providers.

**Claude-only fallback coherence:** When Claude reads a file with one tool family and then edits it with another, tool/model state can drift. If an MCP edit tool is unavailable and you fall back to native editing, re-read the file with the native tool family immediately before editing.

#### Parallel Tool Calls - Claude only

Parallel Read calls fail as a group if any one errors. Before fanning out,
use **Glob** to check existence **FIRST**, THEN read only files that exist.
Do NOT mix the check and the reads in the same batch.

---

## Trusted Support Tools

Trusted support tools are execution infrastructure, not claims to audit. Treat their stdout, stderr, and exit codes as authoritative unless the tool itself reports uncertainty or corruption.

Do NOT bypass, duplicate, or re-run through lower-level tools to "make sure." Re-run only after a relevant state change, or when the tool output explicitly instructs a retry.

**pre-commit** is a trusted quality gate and auto-fix runner. If it modifies files, stage the modified files, then run pre-commit once more. Do NOT manually invoke underlying formatters such as prettier unless pre-commit reports an actionable formatter/tooling error.

---

Secret word: Empowered
