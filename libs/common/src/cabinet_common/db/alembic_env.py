"""Общий `env.py` Alembic: async psycopg 3, версия миграций в собственной схеме сервиса."""

from typing import Any

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import URL, Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from cabinet_common.db.migrate import run_coro
from cabinet_common.db.schemas import SPECS

# Один ключ на все миграции: параллельные запуски (init и ручной `make migrate`) идут по очереди.
ADVISORY_LOCK_KEY = 7_020_300


def _migrate(connection: Connection, schema: str) -> None:
    if schema not in SPECS:
        raise ValueError(f"unknown schema: {schema}")
    connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
    connection.execute(text(f'SET search_path TO "{schema}", public'))
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=None,
        version_table="alembic_version",
        version_table_schema=schema,
    )
    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.rollback()
        connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY})
        connection.commit()


async def _run_online(url: URL, schema: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_migrate, schema)
    await engine.dispose()


def run(schema: str) -> None:
    """Вызывается из `env.py` каждой среды: `run("core")`."""
    attrs: dict[str, Any] = context.config.attributes
    run_coro(_run_online(attrs["url"], attrs.get("schema", schema)))
