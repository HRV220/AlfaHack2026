"""Реестр топиков из `docs/contracts/events/topics.yaml` (архитектура, раздел 9)."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONTRACTS_DIR_ENV = "CONTRACTS_DIR"


class TopicsError(Exception):
    """`topics.yaml` нельзя прочитать или он не соответствует ожидаемой структуре."""


class TopicDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partitions: int = Field(ge=1)
    replication_factor: int = Field(ge=1)
    retention_hours: int = Field(ge=1)
    dlq_retention_hours: int = Field(ge=1)
    retry_backoff_seconds: tuple[int, ...] = Field(min_length=1)


class TopicSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    name: str
    key: str
    producer: str
    consumers: tuple[str, ...]
    schema_file: str = Field(alias="schema")
    schema_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    requirements: tuple[str, ...] = ()

    @property
    def dlq_name(self) -> str:
        return f"{self.name}.dlq"

    @property
    def subject(self) -> str:
        """Имя subject в Schema Registry."""
        return f"{self.name}-value"


class TopicRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    defaults: TopicDefaults
    topics: tuple[TopicSpec, ...]

    def get(self, name: str) -> TopicSpec:
        for topic in self.topics:
            if topic.name == name:
                return topic
        raise KeyError(f"топик {name!r} не описан в topics.yaml")

    def names(self) -> tuple[str, ...]:
        return tuple(topic.name for topic in self.topics)


def find_contracts_dir() -> Path:
    """`CONTRACTS_DIR` из окружения или `docs/contracts` в ближайшем родителе этого файла."""
    override = os.environ.get(CONTRACTS_DIR_ENV)
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "contracts"
        if (candidate / "events" / "topics.yaml").is_file():
            return candidate
    raise TopicsError(
        f"каталог контрактов не найден: задайте {CONTRACTS_DIR_ENV} или запускайте из репозитория"
    )


def load_topics(contracts_dir: Path | None = None) -> TopicRegistry:
    """Читает `events/topics.yaml`; любая ошибка — `TopicsError` с именем файла."""
    file = (contracts_dir or find_contracts_dir()) / "events" / "topics.yaml"
    try:
        parsed = yaml.safe_load(file.read_bytes())
    except OSError as exc:
        raise TopicsError(f"{file}: не удалось прочитать файл ({exc.strerror or exc})") from exc
    except yaml.YAMLError as exc:
        raise TopicsError(f"{file}: некорректный YAML ({exc})") from exc
    if not isinstance(parsed, dict):
        raise TopicsError(f"{file}: ожидался словарь верхнего уровня")
    try:
        registry = TopicRegistry.model_validate(parsed)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in err['loc']) or '<корень>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise TopicsError(f"{file}: невалидный реестр топиков — {problems}") from exc
    names = registry.names()
    if len(set(names)) != len(names):
        raise TopicsError(f"{file}: повторяющиеся имена топиков")
    return registry
