.PHONY: sync lock-check lint format type test check

sync:
	uv sync --all-packages

lock-check:
	uv lock --check

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

type:
	uv run mypy libs services web

test:
	uv run pytest

check: lock-check lint type test
