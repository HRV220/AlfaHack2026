"""Создание топиков и их DLQ в брокере по `topics.yaml` (идемпотентно)."""

from dataclasses import dataclass

from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient
from confluent_kafka.cimpl import KafkaError, NewTopic

from cabinet_common.events.topics import TopicRegistry

HOUR_MS = 3_600_000


class TopicCreationError(Exception):
    """Брокер отказал в создании одного или нескольких топиков."""


@dataclass(frozen=True)
class TopicsResult:
    created: tuple[str, ...]
    existing: tuple[str, ...]


def planned_topics(registry: TopicRegistry) -> list[NewTopic]:
    """Основной топик и `<топик>.dlq` для каждой записи; срок хранения — из `defaults`."""
    defaults = registry.defaults
    result: list[NewTopic] = []
    for spec in registry.topics:
        for name, hours in (
            (spec.name, defaults.retention_hours),
            (spec.dlq_name, defaults.dlq_retention_hours),
        ):
            result.append(
                NewTopic(
                    name,
                    num_partitions=defaults.partitions,
                    replication_factor=defaults.replication_factor,
                    config={"retention.ms": str(hours * HOUR_MS)},
                )
            )
    return result


def ensure_topics(
    bootstrap_servers: str, registry: TopicRegistry, timeout: float = 30.0
) -> TopicsResult:
    """Создаёт недостающие топики; существующие пропускает, повторный запуск не падает."""
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    futures = admin.create_topics(planned_topics(registry), operation_timeout=timeout)
    created: list[str] = []
    existing: list[str] = []
    failed: list[str] = []
    for name, future in futures.items():
        try:
            future.result(timeout + 5)
            created.append(name)
        except KafkaException as exc:
            error = exc.args[0]
            if error.code() == KafkaError.TOPIC_ALREADY_EXISTS:
                existing.append(name)
            else:
                failed.append(f"{name}: {error.str()}")
    if failed:
        raise TopicCreationError("; ".join(failed))
    return TopicsResult(created=tuple(created), existing=tuple(existing))
