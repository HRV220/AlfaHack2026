"""Init-контейнер на настоящих PostgreSQL и Redpanda (E02-06): seed реестра и полный проход шагов.

Нужны оба хранилища: `make init-test` поднимает их сам (`TEST_PG_*`, `KAFKA_BOOTSTRAP_SERVERS`,
`SCHEMA_REGISTRY_URL`).
"""

import json
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from cabinet_common.db.bootstrap import bootstrap
from cabinet_common.db.migrate import upgrade_all
from cabinet_common.db.schemas import admin_url, service_url
from cabinet_common.init.runner import run_steps
from cabinet_common.init.seed import find_registry_dir, load_cards, upsert_cards
from cabinet_common.init.steps import InitSettings, default_steps
from confluent_kafka.admin import AdminClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = pytest.mark.integration

PG = {
    "host": os.environ.get("TEST_PG_HOST", "localhost"),
    "port": int(os.environ.get("TEST_PG_PORT", "55432")),
    "user": os.environ.get("TEST_PG_USER", "postgres"),
    "password": os.environ.get("TEST_PG_PASSWORD", "pg_admin_test"),
}


@pytest.fixture(scope="module")
def database() -> Iterator[str]:
    name = f"init_{uuid.uuid4().hex[:10]}"
    admin = psycopg.connect(dbname="postgres", autocommit=True, **PG)  # type: ignore[arg-type]
    admin.execute(f'CREATE DATABASE "{name}"')
    env = {
        "POSTGRES_HOST": str(PG["host"]),
        "POSTGRES_PORT": str(PG["port"]),
        "POSTGRES_DB": name,
        "POSTGRES_USER": str(PG["user"]),
        "POSTGRES_PASSWORD": str(PG["password"]),
    }
    with pytest.MonkeyPatch.context() as mp:
        for key, value in env.items():
            mp.setenv(key, value)
        bootstrap(admin_url())
        upgrade_all()
        yield name
    admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    admin.close()


@pytest.fixture
async def core(database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(service_url("core"))
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM registry_snapshot"))
    yield engine
    await engine.dispose()


async def rows(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT inn, name, registry_status FROM registry_snapshot")
        )
        return {row.inn: row for row in result}


async def test_seed_loads_cards_and_repeat_does_not_duplicate(core: AsyncEngine) -> None:
    cards = load_cards()
    first = await upsert_cards(core, cards)
    assert (first.inserted, first.updated) == (3, 0)

    second = await upsert_cards(core, cards)
    assert (second.inserted, second.updated) == (0, 3)
    found = await rows(core)
    assert len(found) == 3
    assert found["7707083893"].registry_status == "ACTIVE"


async def test_seed_covers_llc_ip_and_liquidated(core: AsyncEngine) -> None:
    await upsert_cards(core, load_cards())
    found = await rows(core)
    assert {row.registry_status for row in found.values()} == {"ACTIVE", "LIQUIDATED"}
    assert any(len(inn) == 12 for inn in found)


async def test_changed_card_is_updated_in_place(core: AsyncEngine, tmp_path: Path) -> None:
    await upsert_cards(core, load_cards())
    card = json.loads((find_registry_dir() / "7707083893.json").read_text("utf-8"))
    card["name"] = "ООО «Переименованная компания»"
    (tmp_path / "7707083893.json").write_text(json.dumps(card, ensure_ascii=False), "utf-8")

    result = await upsert_cards(core, load_cards(tmp_path))

    assert (result.inserted, result.updated) == (0, 1)
    found = await rows(core)
    assert found["7707083893"].name == "ООО «Переименованная компания»"
    assert len(found) == 3, "остальные карточки не затронуты"


# --- Полный проход init ------------------------------------------------------------------------

KAFKA = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:55092")
REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:55081")


@pytest.fixture
def empty_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Чистая БД без расширений, ролей и миграций: init должен поднять всё сам."""
    name = f"init_full_{uuid.uuid4().hex[:10]}"
    admin = psycopg.connect(dbname="postgres", autocommit=True, **PG)  # type: ignore[arg-type]
    admin.execute(f'CREATE DATABASE "{name}"')
    env = {
        "POSTGRES_HOST": str(PG["host"]),
        "POSTGRES_PORT": str(PG["port"]),
        "POSTGRES_DB": name,
        "POSTGRES_USER": str(PG["user"]),
        "POSTGRES_PASSWORD": str(PG["password"]),
        "KAFKA_BOOTSTRAP_SERVERS": KAFKA,
        "SCHEMA_REGISTRY_URL": REGISTRY_URL,
        # MLflow и Ollama в тесте нет: шаги должны дать предупреждение, а не упасть
        "MLFLOW_TRACKING_URI": "http://127.0.0.1:1",
        "OLLAMA_URL": "http://127.0.0.1:1",
        "WAIT_TIMEOUT_SEC": "30",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    yield name
    admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    admin.close()


def count_sql(database: str, sql: str) -> int:
    with psycopg.connect(dbname=database, **PG) as conn:  # type: ignore[arg-type]
        row = conn.execute(sql).fetchone()
    assert row is not None
    return int(row[0])


def test_full_init_from_empty_database_and_repeat(empty_database: str) -> None:
    assert run_steps(default_steps(InitSettings())) == 0

    schemas = count_sql(
        empty_database,
        "SELECT count(*) FROM information_schema.schemata "
        "WHERE schema_name IN ('core', 'bank', 'ml', 'docs', 'kb')",
    )
    assert schemas == 5
    assert count_sql(empty_database, "SELECT count(*) FROM core.registry_snapshot") == 3
    topics = set(AdminClient({"bootstrap.servers": KAFKA}).list_topics(timeout=15).topics)
    assert {"document.uploaded", "document.uploaded.dlq", "decision.made.dlq"} <= topics

    # Повторный запуск не падает и не дублирует данные
    assert run_steps(default_steps(InitSettings())) == 0
    assert count_sql(empty_database, "SELECT count(*) FROM core.registry_snapshot") == 3


def test_init_stops_when_required_dependency_is_missing(
    empty_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POSTGRES_PORT", "1")
    monkeypatch.setenv("WAIT_TIMEOUT_SEC", "0.1")
    assert run_steps(default_steps(InitSettings())) == 1
    assert (
        count_sql(empty_database, "SELECT count(*) FROM pg_namespace WHERE nspname = 'core'") == 0
    )
