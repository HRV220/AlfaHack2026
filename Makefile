COMPOSE_FILE ?= deploy/compose/compose.yaml
COMPOSE = docker compose --project-directory . -f $(COMPOSE_FILE)

.PHONY: sync lock-check lint format type test check up down compose-file-check migrate migrate-test er-diagram events-test

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

# Миграции всех схем (bootstrap от суперпользователя POSTGRES_*, затем alembic под ролями схем).
migrate:
	uv run python -c "from cabinet_common.db.bootstrap import bootstrap; from cabinet_common.db.migrate import upgrade_all; from cabinet_common.db.schemas import admin_url; bootstrap(admin_url()); upgrade_all()"

# Тест миграций на одноразовом PostgreSQL в Docker: подъём с нуля, downgrade, изоляция, RLS.
migrate-test:
	bash scripts/with_test_postgres.sh uv run pytest -m integration tests/test_migrations.py

er-diagram:
	bash scripts/with_test_postgres.sh uv run python scripts/_er_run.py

# Топики, схемы, outbox, релей и consumer на одноразовых PostgreSQL и Redpanda в Docker (E02-04).
events-test:
	bash scripts/with_test_postgres.sh bash scripts/with_test_redpanda.sh uv run pytest -m integration tests/test_events_broker.py tests/test_events_flow.py
