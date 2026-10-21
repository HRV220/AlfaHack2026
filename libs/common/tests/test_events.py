import copy
import json
from pathlib import Path
from typing import Any

import pytest
from cabinet_common.events import (
    EventValidationError,
    EventValidator,
    TopicsError,
    build_envelope,
    find_contracts_dir,
    load_topics,
)
from cabinet_common.logging import correlation_id

CONTRACTS = find_contracts_dir()
EXAMPLES = sorted((CONTRACTS / "examples" / "events").glob("*.example.json"))


@pytest.fixture(scope="module")
def validator() -> EventValidator:
    return EventValidator(CONTRACTS)


def load_example(name: str) -> dict[str, Any]:
    file = CONTRACTS / "examples" / "events" / f"{name}.example.json"
    event: dict[str, Any] = json.loads(file.read_text("utf-8"))
    return event


def test_registry_has_eleven_topics_with_dlq() -> None:
    registry = load_topics(CONTRACTS)
    assert len(registry.topics) == 11
    assert registry.defaults.retry_backoff_seconds == (1, 5, 25)
    assert registry.get("document.uploaded").dlq_name == "document.uploaded.dlq"
    assert registry.get("document.uploaded").subject == "document.uploaded-value"


def test_unknown_topic_raises() -> None:
    with pytest.raises(KeyError):
        load_topics(CONTRACTS).get("nope")


def test_broken_topics_file_is_reported(tmp_path: Path) -> None:
    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "topics.yaml").write_text("defaults: {}\ntopics: []\n", "utf-8")
    with pytest.raises(TopicsError, match="topics.yaml"):
        load_topics(tmp_path)


def test_missing_topics_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(TopicsError, match="не удалось прочитать"):
        load_topics(tmp_path)


def test_every_topic_has_an_example() -> None:
    assert len(EXAMPLES) == len(load_topics(CONTRACTS).topics)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.name.split(".example")[0])
def test_contract_examples_are_valid(validator: EventValidator, example: Path) -> None:
    validator.validate(json.loads(example.read_text("utf-8")))


@pytest.mark.parametrize("field", ["event_id", "type", "source", "time", "subject", "data"])
def test_missing_envelope_field_is_rejected(validator: EventValidator, field: str) -> None:
    event = load_example("document.uploaded")
    del event[field]
    with pytest.raises(EventValidationError, match=field):
        validator.validate(event)


def test_extra_envelope_field_is_rejected(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["extra"] = 1
    with pytest.raises(EventValidationError):
        validator.validate(event)


def test_unknown_type_is_rejected(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["type"] = "document.unknown"
    with pytest.raises(EventValidationError, match="type"):
        validator.validate(event)


def test_invalid_data_is_rejected_with_path(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["data"]["size_bytes"] = 0
    with pytest.raises(EventValidationError, match=r"data\.size_bytes"):
        validator.validate(event)


def test_domain_ref_is_enforced(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["data"]["inn"] = "not-an-inn"
    with pytest.raises(EventValidationError, match=r"data\.inn"):
        validator.validate(event)


def test_wrong_producer_is_rejected(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["source"] = "ml-service"
    with pytest.raises(EventValidationError, match="source"):
        validator.validate(event)


def test_subject_must_match_topic_key(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["subject"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(EventValidationError, match="subject"):
        validator.validate(event)


@pytest.mark.parametrize("value", ["2026-10-14T09:00:00", "yesterday"])
def test_time_needs_timezone_and_iso(validator: EventValidator, value: str) -> None:
    event = load_example("document.uploaded")
    event["time"] = value
    with pytest.raises(EventValidationError, match="time"):
        validator.validate(event)


def test_bad_correlation_id_is_rejected(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["correlation_id"] = "abc"
    with pytest.raises(EventValidationError, match="correlation_id"):
        validator.validate(event)


def test_all_problems_are_listed(validator: EventValidator) -> None:
    event = load_example("document.uploaded")
    event["data"]["size_bytes"] = 0
    event["data"]["filename"] = 5
    with pytest.raises(EventValidationError) as info:
        validator.validate(event)
    assert len(info.value.problems) == 2


def test_build_envelope_is_valid_and_keeps_data(validator: EventValidator) -> None:
    example = load_example("document.uploaded")
    topic = validator.topics.get("document.uploaded")
    data = copy.deepcopy(example["data"])
    event = build_envelope(topic, example["subject"], data)
    validator.validate(event)
    assert event["data"] == example["data"]
    assert event["source"] == "core-api"
    assert event["schema_version"] == "1.0.0"


def test_build_envelope_uses_context_correlation_id(validator: EventValidator) -> None:
    example = load_example("document.uploaded")
    topic = validator.topics.get("document.uploaded")
    token = correlation_id.set("a" * 32)
    try:
        event = build_envelope(topic, example["subject"], example["data"])
    finally:
        correlation_id.reset(token)
    assert event["correlation_id"] == "a" * 32


def test_build_envelope_generates_unique_ids(validator: EventValidator) -> None:
    example = load_example("document.uploaded")
    topic = validator.topics.get("document.uploaded")
    first = build_envelope(topic, example["subject"], example["data"])
    second = build_envelope(topic, example["subject"], example["data"])
    assert first["event_id"] != second["event_id"]
    validator.validate(second)
