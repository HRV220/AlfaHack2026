import json
from typing import Any

import pytest
from cabinet_common.events import find_contracts_dir, load_topics
from cabinet_common.events.admin import planned_topics
from cabinet_common.events.registry import build_subject_schema
from jsonschema import Draft202012Validator

CONTRACTS = find_contracts_dir()
REGISTRY = load_topics(CONTRACTS)


def collect_refs(node: Any) -> list[str]:
    if isinstance(node, dict):
        found = [node["$ref"]] if isinstance(node.get("$ref"), str) else []
        return found + [ref for value in node.values() for ref in collect_refs(value)]
    if isinstance(node, list):
        return [ref for item in node for ref in collect_refs(item)]
    return []


def test_planned_topics_are_eleven_plus_dlq() -> None:
    topics = planned_topics(REGISTRY)
    names = [topic.topic for topic in topics]
    assert len(topics) == 22
    assert len(set(names)) == 22
    assert sum(name.endswith(".dlq") for name in names) == 11
    assert {topic.num_partitions for topic in topics} == {3}
    assert {topic.replication_factor for topic in topics} == {1}


def test_retention_differs_for_dlq() -> None:
    config = {
        topic.topic: (topic.config or {})["retention.ms"] for topic in planned_topics(REGISTRY)
    }
    assert config["document.uploaded"] == str(168 * 3_600_000)
    assert config["document.uploaded.dlq"] == str(336 * 3_600_000)


@pytest.mark.parametrize("topic", REGISTRY.topics, ids=lambda topic: topic.name)
def test_subject_schema_is_self_contained(topic: Any) -> None:
    schema = build_subject_schema(CONTRACTS, topic)
    assert all(ref.startswith("#/") for ref in collect_refs(schema))
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["type"]["const"] == topic.name
    assert "$id" not in schema


@pytest.mark.parametrize("topic", REGISTRY.topics, ids=lambda topic: topic.name)
def test_subject_schema_accepts_contract_example(topic: Any) -> None:
    example = CONTRACTS / "examples" / "events" / f"{topic.name}.example.json"
    schema = build_subject_schema(CONTRACTS, topic)
    errors = list(Draft202012Validator(schema).iter_errors(json.loads(example.read_text("utf-8"))))
    assert errors == []


def test_subject_schema_rejects_other_topic_event() -> None:
    uploaded = REGISTRY.get("document.uploaded")
    other = json.loads(
        (CONTRACTS / "examples" / "events" / "document.parsed.example.json").read_text("utf-8")
    )
    schema = build_subject_schema(CONTRACTS, uploaded)
    assert list(Draft202012Validator(schema).iter_errors(other))
