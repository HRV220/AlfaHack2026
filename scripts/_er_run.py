"""Создаёт временную БД, применяет миграции и строит ER-диаграмму (вызывается из `make er-diagram`)."""

import os
import runpy
import uuid
from pathlib import Path

import psycopg
from cabinet_common.db.bootstrap import bootstrap
from cabinet_common.db.migrate import upgrade_all
from cabinet_common.db.schemas import admin_url

host = os.environ.get("TEST_PG_HOST", "localhost")
port = os.environ.get("TEST_PG_PORT", "55432")
user = os.environ.get("TEST_PG_USER", "postgres")
password = os.environ.get("TEST_PG_PASSWORD", "pg_admin_test")
name = f"er_{uuid.uuid4().hex[:8]}"

with psycopg.connect(
    host=host, port=port, user=user, password=password, dbname="postgres", autocommit=True
) as admin:
    admin.execute(f'CREATE DATABASE "{name}"')
    os.environ.update(
        POSTGRES_HOST=host,
        POSTGRES_PORT=port,
        POSTGRES_USER=user,
        POSTGRES_PASSWORD=password,
        POSTGRES_DB=name,
    )
    try:
        bootstrap(admin_url())
        upgrade_all()
        runpy.run_path(str(Path(__file__).with_name("er_diagram.py")), run_name="__main__")
    finally:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
