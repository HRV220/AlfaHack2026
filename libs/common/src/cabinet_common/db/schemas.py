"""Схемы PostgreSQL, их владельцы и каталоги Alembic-сред (архитектура 11.1)."""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL

SCHEMAS = ("core", "bank", "ml", "docs", "kb")


def _migrations_root() -> Path:
    """Корень с `services/`: MIGRATIONS_ROOT (образ) или корень репозитория (исходники)."""
    env = os.environ.get("MIGRATIONS_ROOT")
    if env:
        return Path(env)
    parents = Path(__file__).resolve().parents
    if len(parents) > 5:
        return parents[5]
    raise RuntimeError("MIGRATIONS_ROOT is not set and the repository layout is not found")


@dataclass(frozen=True)
class SchemaSpec:
    schema: str
    service_dir: str

    @property
    def role(self) -> str:
        return f"cabinet_{self.schema}"

    @property
    def password_env(self) -> str:
        return f"DB_{self.schema.upper()}_PASSWORD"

    @property
    def default_password(self) -> str:
        return f"{self.schema}_dev"

    def migrations_dir(self) -> Path:
        return _migrations_root() / "services" / self.service_dir / "migrations" / self.schema


SPECS: dict[str, SchemaSpec] = {
    "core": SchemaSpec("core", "core-api"),
    "kb": SchemaSpec("kb", "core-api"),
    "bank": SchemaSpec("bank", "bank-sim"),
    "ml": SchemaSpec("ml", "ml-service"),
    "docs": SchemaSpec("docs", "doc-service"),
}


def role_password(schema: str) -> str:
    spec = SPECS[schema]
    return os.environ.get(spec.password_env, spec.default_password)


def _base_params() -> tuple[str, int, str]:
    return (
        os.environ.get("POSTGRES_HOST", "localhost"),
        int(os.environ.get("POSTGRES_PORT", "5432")),
        os.environ.get("POSTGRES_DB", "cabinet"),
    )


def service_url(schema: str) -> URL:
    """URL подключения под ролью схемы (psycopg 3, async-драйвер SQLAlchemy)."""
    host, port, database = _base_params()
    return URL.create(
        "postgresql+psycopg",
        username=SPECS[schema].role,
        password=role_password(schema),
        host=host,
        port=port,
        database=database,
    )


def admin_url() -> URL:
    """URL суперпользователя для bootstrap (роли, схемы, расширения)."""
    host, port, database = _base_params()
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("POSTGRES_USER", "cabinet"),
        password=os.environ.get("POSTGRES_PASSWORD", "cabinet_dev"),
        host=host,
        port=port,
        database=database,
    )
