# scaffold

[![CI](https://github.com/Jartan-LLC/scaffold/actions/workflows/ci.yml/badge.svg)](https://github.com/Jartan-LLC/scaffold/actions/workflows/ci.yml)

A production-grade Python repo, already wired: dev container, quality gate, hardened CI,
releases and auto-updates, green on the first push.

Python-first, with Node/JS supported second. For another stack, the Python parts delete
cleanly ([how](docs/onboard.md#not-a-python-project)).

## Quick start

1. [Use this template](https://github.com/new?template_name=scaffold&template_owner=Jartan-LLC),
   then open your new repository in its dev container.
2. Run `/onboard` in Claude Code. It interviews you, configures the project and lists the
   manual steps left. To set up by hand instead, follow the
   [setup checklist](docs/onboard.md).
3. Run `make check`: the lint, type checks, tests, build, audit and docs CI runs.

## What you get

| | On day one |
|---|---|
| [Dev container](.devcontainer/) | Python, Node/pnpm and the project tools preinstalled; CI rebuilds and checks it whenever it changes |
| [Quality gate](Makefile) | `make check` runs lint, type checks, tests, build, dependency audit and docs: the same checks CI runs |
| [Security-first](.github/workflows/) | Actions pinned to exact commits, a security linter for the workflows themselves, token-free PyPI publishing, and an OpenSSF Scorecard security rating |
| [CI & releases](.github/workflows/ci.yml) | CI on every pull request; pushing a version tag publishes a GitHub Release, the PyPI package and multi-arch container images |
| [Auto-updates](.github/dependabot.yml) | Dependabot updates after a 7-day cooldown, minor and patch ones merged automatically; weekly broken-link and vulnerability checks that open, update and close their own issue |
| [AI-ready](CLAUDE.md) | Claude Code working under tiered project rules, and optional [Liza](docs/scaffold.md#liza) multi-agent runs |

Not for you if you want a minimal template: this one is deliberately complete.

Every file, and how the parts work: [docs/scaffold.md](docs/scaffold.md). To pull in later
template improvements, see [Syncing template updates](docs/scaffold.md#syncing-template-updates).

Scaffold is [MIT-licensed](LICENSE); your project picks its own license during setup.
