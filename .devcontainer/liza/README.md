# Liza in the devcontainer

[Liza](https://github.com/liza-mas/liza) adds a behavioral contract, adversarial review
and a multi-agent delivery pipeline on top of Claude Code. This directory installs it,
pinned, and keeps activation local to your clone.

## Overview

- Every container gets the `liza` binary (pinned release, checksum-verified), a real
  `rg`, and Liza's global files in `~/.liza`, a volume kept per project across rebuilds.
- Two switches decide the rest: activating Liza for the clone, and installing its agent
  toolchain.
- Activation writes only local files, so collaborators and CI are unaffected.

## Switches

| Variable | Default | When `true` |
|---|---|---|
| `ACTIVATE_LIZA` | `false` | container create runs [`activate.sh`](activate.sh) |
| `INSTALL_LIZA_TOOLS` | `false` | installs the toolchain below instead of codebase-memory-mcp |

The committed default lives in `devcontainer.json` (`containerEnv`), as
`${localEnv:ACTIVATE_LIZA:false}`. Change the `false` to set the project's default. A
variable of the same name on your host overrides it for you. Either change takes
effect on the next rebuild.

## Activation

`liza` on `PATH` is [`shim.sh`](shim.sh). It passes every command to the real binary
except `init`, which it keeps local:

| Liza writes | Where it lands |
|---|---|
| hooks and permissions (and rtk's and bash-policy's hooks) | `.claude/settings.local.json` |
| the contract | `CLAUDE.local.md` → `~/.liza/CORE.md` |
| skills | links in `.claude/skills/` |
| hook scripts, `.claudeignore` and other new files | excluded in `.git/info/exclude` |

To activate a clone by hand, without the switch (prefix `INSTALL_LIZA_TOOLS=true` to
install the toolchain first):

```bash
bash .devcontainer/liza/activate.sh
```

The shim covers any `liza init`, including the multi-agent one below, and loads the
toolchain's `LIZA_ENABLE_*` gates for it when `INSTALL_LIZA_TOOLS` is on.
`~/.liza/libexec/liza init` bypasses it and writes to the committed
`.claude/settings.json` and to `~/.claude/CLAUDE.md`.

## Modes

Each Claude session selects its mode at start; start a new session to switch.

| Mode | For | Start it |
|---|---|---|
| Pairing | everyday work; you approve each step | open Claude in an activated clone |
| Adversarial Pairing | one high-stakes change, reviewed by separate sessions | see below |
| Multi-agent | a goal large enough to decompose and run unattended | see below |

**Adversarial Pairing.** Open one Claude session per role and keep its files in
`.adversarial/`, because a multi-agent init deletes `.liza/` and `.worktrees/`:

```text
/adversarial-pairing doer .adversarial/<name>.md
/adversarial-pairing reviewer-1 .adversarial/<name>.md
```

When the doer asks where to create its worktree, answer `.adversarial/worktrees/<name>`.

**Multi-agent.** Commit a goal document first, then:

```bash
liza init "<goal>" --spec specs/<goal>.md --post-worktree-cmd "make deps"
liza tui
```

`make deps` gives each task worktree its own virtualenv; `make install` would fail there,
since Liza sets the worktree's `core.hooksPath` and `pre-commit install` refuses that. Fill in
[`GUARDRAILS.md`](../../GUARDRAILS.md) before a first run. Liza's
[Getting Started](https://github.com/liza-mas/liza/blob/main/GETTING_STARTED.md) covers
the rest of the run: checkpoints, the operator session, logs.

## Toolchain

With `INSTALL_LIZA_TOOLS=true`, [`tools.sh`](tools.sh) installs these into
`~/.liza/bin`, every one pinned, and writes the `LIZA_ENABLE_*` switches Liza reads to
`~/.liza/toolchain/env.sh`, which `.bashrc` and `.profile` source.

| Tool | Installed from | Notes |
|---|---|---|
| ast-grep, yq | release binary + sha256 | |
| rtk, mdq | release binary + sha256 | x86_64 only; skipped on arm64 (scaffold issue 124) |
| stacklit, scip-search, functional-clusters, mdtoc, bash-policy | source at a pinned commit, built with the Go feature | no upstream release binaries |
| scip-python, scip-typescript, context7 MCP | [`npm/package-lock.json`](npm/package-lock.json) | context7 registered at local scope |
| semble | [`semble-requirements.txt`](semble-requirements.txt) (hash-locked) | model pinned by revision and sha256; never downloads at runtime |

- It turns codebase-memory-mcp off for this project, as `/mcp` would; Liza forbids
  workspace-level tools in its worktrees.
- scip-python indexes project code; it sees third-party packages only through `pip`,
  which uv virtualenvs don't include.
- Liza's own `liza toolchain install` is not used: it fetches unpinned installers from
  upstream default branches.
- Agents read [`AGENT_TOOLS.md`](AGENT_TOOLS.md), or
  [`AGENT_TOOLS.minimal.md`](AGENT_TOOLS.minimal.md) without the toolchain. Each lists
  only what is installed, since the contract has agents search for any listed tool that is
  missing before falling back.

## Updating pins

| Pin | Where | Then |
|---|---|---|
| Liza release | `LIZA_RELEASE` in [`install.sh`](install.sh) | the recipe in its header |
| ripgrep, release binaries, semble model | [`install.sh`](install.sh), [`tools.sh`](tools.sh) | recompute the sha256 of the new asset |
| source-built tools | `GO_TOOLS` in [`tools.sh`](tools.sh) | set the new commit SHA |
| npm tools | [`npm/package.json`](npm/package.json) | `npm install --package-lock-only` in `npm/` |
| semble | [`semble-requirements.txt`](semble-requirements.txt) | the command in its header |
| `AGENT_TOOLS*.md` | both variants here | diff upstream `contracts/AGENT_TOOLS.md` between the old and new Liza tags; carry the changes into both |

Then run [`smoke-test.sh`](smoke-test.sh), which activates a throwaway clone and checks
activation stays local and idempotent; CI runs it on every change to this directory.

## Removing Liza

1. Delete this directory and `.github/workflows/liza-smoke.yml`.
2. In `devcontainer.json`, drop the `liza-${devcontainerId}` mount, the two switches and
   the Go feature (its entry in `devcontainer-lock.json` too).
3. In `post-create.sh`, drop the Liza block, the "Liza is installed but not active" note,
   and the `INSTALL_LIZA_TOOLS` condition on codebase-memory-mcp.
4. Delete the Liza section of `.gitignore`; drop the Liza mention and checklist item from
   `README.md` and the Liza parts of `.claude/commands/onboard.md`. Keep `GUARDRAILS.md`:
   it holds the project rules.
5. In each clone that was activated: delete `CLAUDE.local.md`, the Liza entries in
   `.claude/settings.local.json`, the `.claude/skills/` links into `~/.liza` and Liza's
   `.claude/hooks/` scripts, and the Liza lines in `.git/info/exclude`. If the toolchain was
   on, run `claude mcp remove --scope local context7` and re-enable codebase-memory-mcp with
   `/mcp`.
6. Remove the volume from the host: `docker volume rm liza-<devcontainerId>`.

## See also

- Upstream issues this works around: liza-mas/liza
  [163](https://github.com/liza-mas/liza/issues/163) and
  [164](https://github.com/liza-mas/liza/issues/164)
- [Adversarial Pairing](https://github.com/liza-mas/liza/blob/main/support-docs/ADVERSARIAL_PAIRING.md)
  and [Multi-Agent Usage](https://github.com/liza-mas/liza/blob/main/support-docs/USAGE_MULTI_AGENTS.md)
