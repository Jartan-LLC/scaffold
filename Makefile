# Task runner for the local dev loop. Run `make` or `make help` to list targets.
.PHONY: help install lint fix typecheck test test-integration docs check all

# uv replaces pip as this project's installer, resolver, venv manager and build
# frontend. Install it once — https://docs.astral.sh/uv/getting-started/installation/
# — and every target below runs out of ./.venv without a shell activation,
# because the venv's bin directory goes on PATH for this whole file. That also
# makes pyright pick the venv's interpreter, which it otherwise would not.
# A missing .venv just falls through to the ambient interpreter, so `make lint`
# still works in a container that installed the toolchain system-wide.
export PATH := $(CURDIR)/.venv/bin:$(PATH)

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

# Order-only prerequisite below: created when absent, never rebuilt when stale.
.venv:
	@command -v uv >/dev/null || { echo "uv not found — install it: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv venv

install: | .venv  ## Create .venv, install the package + dev extras, wire the pre-commit hook
	uv pip install -e '.[dev]' -r ci/requirements.txt
	# Skip hook wiring outside a git checkout (e.g. an unpacked sdist); real failures still surface.
	if git rev-parse --git-dir >/dev/null 2>&1; then pre-commit install; fi

lint:  ## Lint all files via pre-commit (ruff, codespell, shellcheck, markdownlint, lychee, actionlint, zizmor, hygiene)
	pre-commit run --all-files

fix:  ## Auto-format and apply ruff's safe fixes
	ruff format .
	ruff check --fix .

typecheck:  ## Static type check (pyright, strict)
	pyright

test:  ## Run the unit suite (matches CI: excludes integration-marked tests)
	pytest -m "not integration"

test-integration:  ## Run only integration-marked tests
	pytest -m integration

docs:  ## Build the docs site, warnings-as-errors (needs the docs extra)
	sphinx-build -W -b html docs docs/_build/html

# The one gate: reproduces every CI check locally on the active interpreter
# (CI additionally sweeps the 3.12/3.13 matrix — see ci.yml). Self-installs the
# CI-only tools (pre-commit, twine, pip-audit) that are kept out of the dev
# extras — they are exact-pinned in ci/requirements.txt, the same file CI
# installs from, so this gate and that one run identical tools.
check: | .venv  ## Run every CI check (lint, typecheck, test, build, audit, docs)
	uv pip install -q -e '.[dev,docs]' -r ci/requirements.txt
	$(MAKE) lint typecheck test
	uv build
	python -m twine check dist/*
	pip-audit
	$(MAKE) docs

all: check  ## Alias for `check`
