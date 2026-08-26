# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `post-attach.sh` now reconciles the plugins `.claude/settings.json` declares
  against the shared `~/.claude` volume instead of only updating what was
  already installed. Install records are keyed by project path, so a new project
  got no plugins and had to be fixed by hand on every clone. Declared
  marketplaces are registered at their declared ref, missing plugins are
  installed at `local` scope, and the update pass no longer touches other
  projects' records. Marketplace registration is scoped to `local` too, so one
  project's declaration is not written into the shared volume's settings, and
  declarations are read from the tracked `settings.json` alone — the gitignored
  `settings.local.json` is the install record, not a policy source, so removing
  a plugin upstream is not overridden by a container's own history.

<!-- Add ### Added / ### Changed / ### Fixed sections here as you make changes. -->
<!-- Update ORG/REPO (or let /onboard do it). -->
[Unreleased]: https://github.com/ORG/REPO/commits/main
