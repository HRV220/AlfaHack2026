"""Bootstrap БД от суперпользователя: расширения, роли, схемы. Идемпотентен (E02-03.1, E02-03.2)."""

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

from cabinet_common.db.schemas import SPECS, role_password

EXTENSIONS = ("vector", "pgcrypto")


def bootstrap(admin: URL) -> None:
    with psycopg.connect(
        host=admin.host,
        port=admin.port,
        dbname=admin.database,
        user=admin.username,
        password=admin.password,
        autocommit=True,
    ) as conn:
        conn.execute("SELECT pg_advisory_lock(7020301)")
        for ext in EXTENSIONS:
            conn.execute(sql.SQL("CREATE EXTENSION IF NOT EXISTS {}").format(sql.Identifier(ext)))
        for spec in SPECS.values():
            role = sql.Identifier(spec.role)
            schema = sql.Identifier(spec.schema)
            password = sql.Literal(role_password(spec.schema))
            exists = conn.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (spec.role,)
            ).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(
                sql.SQL("{} ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                    sql.SQL(verb), role, password
                )
            )
            conn.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(schema, role)
            )
            conn.execute(sql.SQL("ALTER SCHEMA {} OWNER TO {}").format(schema, role))
            # Чужие схемы недоступны: USAGE у схемы есть только у владельца.
            conn.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(schema))
            conn.execute(sql.SQL("ALTER ROLE {} SET search_path = {}, public").format(role, schema))
