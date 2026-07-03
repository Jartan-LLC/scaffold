# Task runner for the local dev loop. Run `make` or `make help` to list targets.
.PHONY: help install lint fix typecheck test docs check all

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install the package with its dev extras
	pip install -e '.[dev]'

lint:  ## Lint without modifying: ruff, codespell, shellcheck, markdownlint
	ruff check .
	ruff format --check .
	codespell
	find . -name "*.sh" -not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/vendor/*" -print0 | xargs -r -0 shellcheck
	npx --yes markdownlint-cli2

fix:  ## Auto-format and apply ruff's safe fixes
	ruff format .
	ruff check --fix .

typecheck:  ## Static type check (pyright, strict)
	pyright

test:  ## Run the test suite
	pytest

docs:  ## Build the docs site, warnings-as-errors (needs the docs extra)
	sphinx-build -W -b html docs docs/_build/html

# The one gate: reproduces every CI check locally. Self-installs the CI-only
# tools (build, twine, pip-audit) that are kept out of the dev extras.
check:  ## Run every CI check (lint, typecheck, test, build, audit, docs)
	pip install -q -e '.[dev,docs]' build twine pip-audit
	$(MAKE) lint typecheck test
	python -m build
	python -m twine check dist/*
	pip-audit
	sphinx-build -W -b html docs docs/_build/html

all: check  ## Alias for `check`
