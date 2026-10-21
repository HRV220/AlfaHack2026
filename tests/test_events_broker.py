"""Топики и схемы на настоящем Redpanda (E02-04.1, E02-04.2).

Нужен брокер: `make events-test` поднимает его сам и задаёт `KAFKA_BOOTSTRAP_SERVERS`
и `SCHEMA_REGISTRY_URL`.
"""

import os

import pytest
from cabinet_common.events import find_contracts_dir, load_topics
from cabinet_common.events.admin import ensure_topics
from cabinet_common.events.cli import main as cli_main
from cabinet_common.events.registry import (
    SchemaRegistryClient,
    SchemaRegistryError,
    SchemaStatus,
    build_subject_schema,
    register_all,
)
from confluent_kafka.admin import AdminClient

pytestmark = pytest.mark.integration

KAFKA = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:55092")
REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:55081")
CONTRACTS = find_contracts_dir()
TOPICS = load_topics(CONTRACTS)


def broker_topics() -> set[str]:
    metadata = AdminClient({"bootstrap.servers": KAFKA}).list_topics(timeout=15)
    return set(metadata.topics)


def test_topics_are_created_and_repeat_is_noop() -> None:
    first = ensure_topics(KAFKA, TOPICS)
    expected = {name for spec in TOPICS.topics for name in (spec.name, spec.dlq_name)}
    assert expected <= broker_topics()
    assert len(first.created) + len(first.existing) == 22

    second = ensure_topics(KAFKA, TOPICS)
    assert second.created == ()
    assert len(second.existing) == 22


def test_partitions_match_registry() -> None:
    ensure_topics(KAFKA, TOPICS)
    metadata = AdminClient({"bootstrap.servers": KAFKA}).list_topics(timeout=15)
    assert len(metadata.topics["decision.made"].partitions) == TOPICS.defaults.partitions
    assert len(metadata.topics["decision.made.dlq"].partitions) == TOPICS.defaults.partitions


def test_schemas_registered_once_and_repeat_is_noop() -> None:
    first = register_all(REGISTRY_URL, CONTRACTS, TOPICS)
    assert len(first) == 11

    second = register_all(REGISTRY_URL, CONTRACTS, TOPICS)
    assert {item.status for item in second} == {SchemaStatus.UNCHANGED}
    assert [item.schema_id for item in second] == [item.schema_id for item in first]

    client = SchemaRegistryClient(REGISTRY_URL)
    try:
        subjects = set(client.subjects())
    finally:
        client.close()
    assert {spec.subject for spec in TOPICS.topics} <= subjects


def test_changed_schema_gets_new_version() -> None:
    topic = TOPICS.get("document.uploaded")
    schema = build_subject_schema(CONTRACTS, topic)
    schema["properties"]["data"]["properties"]["comment"] = {"type": "string"}
    client = SchemaRegistryClient(REGISTRY_URL)
    try:
        before = client.register(topic.subject, build_subject_schema(CONTRACTS, topic))
        changed = client.register(topic.subject, schema)
    finally:
        client.close()
    assert changed.status is SchemaStatus.REGISTERED
    assert changed.schema_id != before.schema_id


def test_incompatible_schema_is_rejected() -> None:
    topic = TOPICS.get("document.parsed")
    register_all(REGISTRY_URL, CONTRACTS, TOPICS)
    schema = build_subject_schema(CONTRACTS, topic)
    properties = schema["properties"]["data"]["properties"]
    properties["document_id"] = {"type": "boolean"}
    client = SchemaRegistryClient(REGISTRY_URL)
    try:
        with pytest.raises(SchemaRegistryError):
            client.register(topic.subject, schema)
    finally:
        client.close()


def test_cli_all_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA)
    monkeypatch.setenv("SCHEMA_REGISTRY_URL", REGISTRY_URL)
    assert cli_main(["all"]) == 0
    assert cli_main(["all"]) == 0
