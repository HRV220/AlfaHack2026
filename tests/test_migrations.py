"""Миграции БД (E02-03): подъём с нуля, откат, изоляция схем, неизменяемость снимков, RLS.

Нужен PostgreSQL с pgvector и суперпользователем: `make migrate-test` поднимает его сам.
Параметры подключения — `TEST_PG_HOST|PORT|USER|PASSWORD`.
"""

import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from cabinet_common.db.bootstrap import bootstrap
from cabinet_common.db.migrate import downgrade, upgrade, upgrade_all
from cabinet_common.db.schemas import SPECS, admin_url, role_password
from psycopg import errors

pytestmark = pytest.mark.integration

ADMIN = {
    "host": os.environ.get("TEST_PG_HOST", "localhost"),
    "port": int(os.environ.get("TEST_PG_PORT", "55432")),
    "user": os.environ.get("TEST_PG_USER", "postgres"),
    "password": os.environ.get("TEST_PG_PASSWORD", "pg_admin_test"),
}
INN_A = "7707083893"
INN_B = "500100732259"


def _connect(dbname: str, **overrides: object) -> psycopg.Connection:
    params = {**ADMIN, "dbname": dbname, **overrides}
    return psycopg.connect(**params)  # type: ignore[arg-type]


def _as_role(dbname: str, schema: str) -> psycopg.Connection:
    return _connect(dbname, user=SPECS[schema].role, password=role_password(schema))


@pytest.fixture(scope="module")
def database() -> Iterator[str]:
    name = f"mig_{uuid.uuid4().hex[:10]}"
    try:
        admin = _connect("postgres", autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.fail(f"PostgreSQL недоступен ({ADMIN['host']}:{ADMIN['port']}): {exc}")
    admin.execute(f'CREATE DATABASE "{name}"')
    env = {
        "POSTGRES_HOST": str(ADMIN["host"]),
        "POSTGRES_PORT": str(ADMIN["port"]),
        "POSTGRES_DB": name,
        "POSTGRES_USER": str(ADMIN["user"]),
        "POSTGRES_PASSWORD": str(ADMIN["password"]),
    }
    with pytest.MonkeyPatch.context() as mp:
        for key, value in env.items():
            mp.setenv(key, value)
        bootstrap(admin_url())
        upgrade_all()
        yield name
    admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    admin.close()


def test_bootstrap_is_idempotent(database: str) -> None:
    bootstrap(admin_url())
    with _connect(database) as conn:
        roles = {r[0] for r in conn.execute("SELECT rolname FROM pg_roles")}
        exts = {r[0] for r in conn.execute("SELECT extname FROM pg_extension")}
    assert {spec.role for spec in SPECS.values()} <= roles
    assert {"vector", "pgcrypto"} <= exts


def test_every_schema_has_its_own_version_table(database: str) -> None:
    with _connect(database) as conn:
        for schema in SPECS:
            (head,) = conn.execute(f'SELECT version_num FROM "{schema}".alembic_version').fetchone()  # type: ignore[misc]
            assert head.startswith(f"{schema}_")


@pytest.mark.parametrize("own", list(SPECS))
def test_role_cannot_read_foreign_schema(database: str, own: str) -> None:
    probes = {
        "core": "company",
        "bank": "account",
        "ml": "forecast",
        "docs": "parse_job",
        "kb": "article",
    }
    with _as_role(database, own) as conn:
        for schema, table in probes.items():
            if schema == own:
                conn.execute(f'SELECT 1 FROM "{schema}".{table} LIMIT 1')
                continue
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(f'SELECT 1 FROM "{schema}".{table} LIMIT 1')
            conn.rollback()


def test_no_cross_schema_foreign_keys(database: str) -> None:
    with _connect(database) as conn:
        rows = conn.execute(
            """
            SELECT c.conrelid::regclass::text, c.confrelid::regclass::text
            FROM pg_constraint c
            JOIN pg_class src ON src.oid = c.conrelid
            JOIN pg_class dst ON dst.oid = c.confrelid
            WHERE c.contype = 'f' AND src.relnamespace <> dst.relnamespace
            """
        ).fetchall()
    assert rows == []


def test_kb_has_fulltext_and_vector_indexes(database: str) -> None:
    with _connect(database) as conn:
        defs = " ".join(
            r[0] for r in conn.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = 'kb'")
        )
    assert "USING gin (tsv)" in defs
    assert "USING hnsw (embedding vector_cosine_ops)" in defs


def _new_company(conn: psycopg.Connection, inn: str) -> uuid.UUID:
    company_id = uuid.uuid4()
    conn.execute("SELECT set_config('app.company_id', %s, true)", (str(company_id),))
    conn.execute("INSERT INTO company (id, inn) VALUES (%s, %s)", (company_id, inn))
    return company_id


def _new_recommendation(conn: psycopg.Connection, company_id: uuid.UUID) -> uuid.UUID:
    need_id, rec_id = uuid.uuid4(), uuid.uuid4()
    conn.execute(
        "INSERT INTO need (id, company_id, version, origin, fields) VALUES (%s, %s, 1, 'TEXT', '{}')",
        (need_id, company_id),
    )
    conn.execute(
        """INSERT INTO recommendation (id, company_id, need_id, trigger, need_snapshot,
               profile_version, weights_profile, evaluations, versions, latency_ms)
           VALUES (%s, %s, %s, 'NEED', '{}', 'p1', 'BALANCED', '[]', '{}', 10)""",
        (rec_id, company_id, need_id),
    )
    return rec_id


def test_rls_isolates_companies(database: str) -> None:
    with _as_role(database, "core") as conn:
        company_a = _new_company(conn, INN_A)
        _new_recommendation(conn, company_a)
        conn.commit()
        company_b = _new_company(conn, INN_B)
        conn.commit()

        # Под компанией B чужих строк нет.
        conn.execute("SELECT set_config('app.company_id', %s, true)", (str(company_b),))
        assert conn.execute("SELECT count(*) FROM need").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM recommendation").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM company").fetchone() == (1,)
        conn.commit()

        # Под компанией A своя строка видна.
        conn.execute("SELECT set_config('app.company_id', %s, true)", (str(company_a),))
        assert conn.execute("SELECT count(*) FROM need").fetchone() == (1,)
        conn.commit()

        # Без company_id не видно ничего.
        assert conn.execute("SELECT count(*) FROM company").fetchone() == (0,)

        # Писать строку чужой компании нельзя.
        conn.execute("SELECT set_config('app.company_id', %s, true)", (str(company_b),))
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO need (company_id, version, origin, fields) VALUES (%s, 1, 'TEXT', '{}')",
                (company_a,),
            )
        conn.rollback()


def test_recommendation_is_immutable(database: str) -> None:
    with _as_role(database, "core") as conn:
        company_id = _new_company(conn, "7728168971")
        rec_id = _new_recommendation(conn, company_id)
        conn.commit()
        conn.execute("SELECT set_config('app.company_id', %s, false)", (str(company_id),))
        with pytest.raises(errors.IntegrityConstraintViolation):
            conn.execute("UPDATE recommendation SET latency_ms = 1 WHERE id = %s", (rec_id,))
        conn.rollback()
        conn.execute("SELECT set_config('app.company_id', %s, false)", (str(company_id),))
        with pytest.raises(errors.IntegrityConstraintViolation):
            conn.execute("DELETE FROM recommendation WHERE id = %s", (rec_id,))
        conn.rollback()
        with pytest.raises(errors.IntegrityConstraintViolation):
            conn.execute("TRUNCATE recommendation CASCADE")
        conn.rollback()


def test_decision_snapshot_is_immutable_except_review_fields(database: str) -> None:
    with _as_role(database, "core") as conn:
        company_id = _new_company(conn, "7810000014")
        rec_id = _new_recommendation(conn, company_id)
        app_id, decision_id = uuid.uuid4(), uuid.uuid4()
        conn.execute(
            "INSERT INTO application (id, company_id, recommendation_id) VALUES (%s, %s, %s)",
            (app_id, company_id, rec_id),
        )
        conn.execute(
            """INSERT INTO decision (id, application_id, application_version, company_id, outcome,
                   amount_requested, term_months, recommendation_id, versions, decided_at)
               VALUES (%s, %s, 1, %s, 'APPROVED', 100000, 12, %s, '{}', now())""",
            (decision_id, app_id, company_id, rec_id),
        )
        conn.commit()
        conn.execute("SELECT set_config('app.company_id', %s, false)", (str(company_id),))

        conn.execute("UPDATE decision SET final_outcome = 'APPROVED' WHERE id = %s", (decision_id,))
        conn.commit()
        conn.execute("SELECT set_config('app.company_id', %s, false)", (str(company_id),))
        with pytest.raises(errors.IntegrityConstraintViolation):
            conn.execute("UPDATE decision SET amount_requested = 1 WHERE id = %s", (decision_id,))
        conn.rollback()
        conn.execute("SELECT set_config('app.company_id', %s, false)", (str(company_id),))
        with pytest.raises(errors.IntegrityConstraintViolation):
            conn.execute("DELETE FROM decision WHERE id = %s", (decision_id,))
        conn.rollback()


def _head(database: str, schema: str) -> str:
    with _connect(database) as conn:
        row = conn.execute(f'SELECT version_num FROM "{schema}".alembic_version').fetchone()
    assert row is not None
    return str(row[0])


@pytest.mark.parametrize("schema", list(SPECS))
def test_downgrade_one_step_and_upgrade_again(database: str, schema: str) -> None:
    head = _head(database, schema)
    downgrade(schema, "-1")
    with _connect(database) as conn:
        count = conn.execute(f'SELECT count(*) FROM "{schema}".alembic_version').fetchone()
    # Одноверсионные схемы откатываются до base (строки версии нет), остальные — на шаг назад.
    assert count == (0,) or _head(database, schema) != head
    upgrade(schema)
    assert _head(database, schema) == head


def test_rls_downgrade_removes_policies(database: str) -> None:
    downgrade("core", "-1")
    with _connect(database) as conn:
        policies = conn.execute(
            "SELECT count(*) FROM pg_policies WHERE schemaname = 'core'"
        ).fetchone()
        funcs = conn.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'core' AND p.proname = 'current_company_id'"
        ).fetchone()
    upgrade("core")
    assert policies == (0,)
    assert funcs == (0,)


def test_login_by_inn_finds_only_that_company(database: str) -> None:
    with _as_role(database, "core") as conn:
        company_id = _new_company(conn, "7743013901")
        conn.commit()
        assert conn.execute("SELECT count(*) FROM company WHERE inn = '7743013901'").fetchone() == (
            0,
        )
        conn.execute("SELECT set_config('app.login_inn', '7743013901', true)")
        assert conn.execute("SELECT id FROM company").fetchall() == [(company_id,)]
        conn.commit()


@pytest.mark.parametrize("schema", list(SPECS))
def test_full_downgrade_leaves_only_version_table(database: str, schema: str) -> None:
    downgrade(schema, "base")
    with _connect(database) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                (schema,),
            )
        }
    upgrade(schema)
    assert tables <= {"alembic_version"}
