"""Экспорт ER-диаграммы по схемам из применённых миграций в docs/data-model/ (E02-03.11).

Читает БД из переменных POSTGRES_* (после `bootstrap` и `upgrade_all`) и пишет Mermaid `erDiagram`.
"""

import sys
from pathlib import Path

import psycopg
from cabinet_common.db.schemas import SPECS, admin_url

OUT = Path(__file__).resolve().parents[1] / "docs" / "data-model"


def render(conn: psycopg.Connection, schema: str) -> str:
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE' AND table_name <> 'alembic_version' "
            "ORDER BY table_name",
            (schema,),
        )
    ]
    pks = {
        (r[0], r[1])
        for r in conn.execute(
            "SELECT tc.table_name, kcu.column_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu USING (constraint_schema, constraint_name) "
            "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s",
            (schema,),
        )
    }
    lines = ["erDiagram"]
    for table in tables:
        lines.append(f"  {table} {{")
        cols = conn.execute(
            "SELECT column_name, data_type, udt_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table),
        )
        for name, data_type, udt in cols:
            dtype = udt if data_type in ("ARRAY", "USER-DEFINED") else data_type
            dtype = dtype.replace(" ", "_")
            key = " PK" if (table, name) in pks else ""
            lines.append(f"    {dtype} {name}{key}")
        lines.append("  }")
    fks = conn.execute(
        "SELECT DISTINCT src.relname, dst.relname FROM pg_constraint c "
        "JOIN pg_class src ON src.oid = c.conrelid JOIN pg_class dst ON dst.oid = c.confrelid "
        "JOIN pg_namespace n ON n.oid = src.relnamespace "
        "WHERE c.contype = 'f' AND n.nspname = %s ORDER BY 1, 2",
        (schema,),
    )
    for src, dst in fks:
        lines.append(f"  {dst} ||--o{{ {src} : has")
    return "\n".join(lines)


def main() -> None:
    url = admin_url()
    OUT.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(
        host=url.host, port=url.port, dbname=url.database, user=url.username, password=url.password
    ) as conn:
        for schema in SPECS:
            body = render(conn, schema)
            text = (
                f"# Схема `{schema}` — ER-диаграмма\n\n"
                "Файл создан скриптом `scripts/er_diagram.py` из применённых миграций (`make er-diagram`); "
                "вручную не править.\n\n"
                f"```mermaid\n{body}\n```\n"
            )
            (OUT / f"er-{schema}.md").write_text(text, encoding="utf-8", newline="\n")
            print(f"{schema}: {OUT / f'er-{schema}.md'}")


if __name__ == "__main__":
    sys.exit(main())
