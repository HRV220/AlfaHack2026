"""Запуск Alembic по схеме: `upgrade`/`downgrade` под ролью-владельцем схемы."""

import asyncio
import sys
from collections.abc import Coroutine
from typing import Any

from alembic import command
from alembic.config import Config

from cabinet_common.db.schemas import SPECS, service_url


def run_coro(coro: Coroutine[Any, Any, None]) -> None:
    """Запускает корутину; на Windows psycopg требует SelectorEventLoop."""
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=factory) as runner:
        runner.run(coro)


def _config(schema: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(SPECS[schema].migrations_dir()))
    cfg.attributes["schema"] = schema
    cfg.attributes["url"] = service_url(schema)
    return cfg


def upgrade(schema: str, revision: str = "head") -> None:
    command.upgrade(_config(schema), revision)


def downgrade(schema: str, revision: str = "-1") -> None:
    command.downgrade(_config(schema), revision)


def upgrade_all() -> None:
    """Порядок: схемы независимы, но `core` идёт первой — как в init (E02-06)."""
    for schema in SPECS:
        upgrade(schema)
