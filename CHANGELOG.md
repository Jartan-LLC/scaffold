# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Pin Node.js to v24 in devcontainer to avoid corepack removal in Node 26 (#105)
- Add npm-based pnpm fallback in post-create.sh when corepack is absent
- Update CI snippet to use `pnpm/setup` (successor to `pnpm/action-setup`) with `NPM_CONFIG_AUDIT=false` to prevent npm audit stall

[Unreleased]: https://github.com/ORG/REPO/commits/main
