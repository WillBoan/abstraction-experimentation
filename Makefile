.PHONY: help setup sync lint format typecheck test check eval-dsl clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup:  ## Init submodules and install everything (incl. dev + llm extras)
	git submodule update --init --recursive
	uv sync --extra llm

sync:  ## Install/update dependencies
	uv sync

lint:  ## Lint with ruff
	uv run ruff check .

format:  ## Auto-format with ruff
	uv run ruff format .
	uv run ruff check --fix .

typecheck:  ## Type-check with mypy --strict
	uv run mypy

test:  ## Run the test suite
	uv run pytest

check: lint typecheck test  ## Lint, type-check, and test

eval-dsl:  ## Score the DSL solver on ARC-1 evaluation
	uv run arc-lab eval dsl --dataset arc1-eval

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
