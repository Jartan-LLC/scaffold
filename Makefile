# Task runner wrapping the Verify commands. Run `make` or `make help` for the list.
.PHONY: help install lint fix typecheck test check all

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install the package with dev extras
	pip install -e '.[dev]'

lint:  ## Lint without modifying (mirrors CI): ruff + codespell
	ruff check .
	ruff format --check .
	codespell

fix:  ## Auto-format and apply safe fixes
	ruff format .
	ruff check --fix .

typecheck:  ## Static type check (pyright strict)
	pyright

test:  ## Run the test suite
	pytest

check: lint typecheck test  ## Run every CI check locally

all: check  ## Alias for `check`
