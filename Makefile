# Task runner for the local dev loop. Run `make` or `make help` to list targets.
.PHONY: help install lint fix typecheck test test-integration docs check all

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install the package with its dev extras and wire the pre-commit hook
	pip install -e '.[dev]'
	pre-commit install

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
# CI-only tools (build, twine, pip-audit) that are kept out of the dev extras.
check:  ## Run every CI check (lint, typecheck, test, build, audit, docs)
	pip install -q -e '.[dev,docs]' build twine pip-audit
	$(MAKE) lint typecheck test
	python -m build
	python -m twine check dist/*
	pip-audit
	$(MAKE) docs

all: check  ## Alias for `check`
