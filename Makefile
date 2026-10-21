COMPOSE_FILE ?= deploy/compose/compose.yaml
COMPOSE = docker compose --project-directory . -f $(COMPOSE_FILE)

.PHONY: sync lock-check lint format type test check up down compose-file-check

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

# Compose-файл появляется в E02-02; до этого цели останавливаются с понятным сообщением.
up down: compose-file-check

up:
	$(COMPOSE) --profile core up -d --build

down:
	$(COMPOSE) --profile core down

compose-file-check:
	@test -f $(COMPOSE_FILE) || { echo "$(COMPOSE_FILE) not found: the core profile is added in E02-02"; exit 1; }
