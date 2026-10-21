"""Проверка конверта и `data` по JSON Schema из `docs/contracts/` (до публикации и после чтения)."""

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from cabinet_common.events.topics import TopicRegistry, find_contracts_dir, load_topics

ENVELOPE_FILE = "envelope.schema.json"


class EventValidationError(Exception):
    """Событие не соответствует контракту; `problems` — список понятных причин."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def load_schema_registry(contracts_dir: Path) -> Registry[Any]:
    """Все `*.schema.json` каталога контрактов по `$id`: относительные `$ref` разрешаются."""
    registry: Registry[Any] = Registry()
    for file in sorted(contracts_dir.rglob("*.schema.json")):
        contents = json.loads(file.read_text(encoding="utf-8"))
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        registry = registry.with_resource(uri=contents["$id"], resource=resource)
    return registry


class EventValidator:
    def __init__(self, contracts_dir: Path | None = None) -> None:
        root = contracts_dir or find_contracts_dir()
        self.topics: TopicRegistry = load_topics(root)
        self._registry = load_schema_registry(root)
        events_dir = root / "events"
        self._envelope = self._validator(
            json.loads((events_dir / ENVELOPE_FILE).read_text("utf-8"))
        )
        self._data: dict[str, Draft202012Validator] = {
            topic.name: self._validator(
                json.loads((events_dir / topic.schema_file).read_text("utf-8"))
            )
            for topic in self.topics.topics
        }

    def _validator(self, schema: dict[str, Any]) -> Draft202012Validator:
        return Draft202012Validator(schema, registry=self._registry)

    def validate(self, event: Mapping[str, Any]) -> None:
        """Бросает `EventValidationError`: неверный конверт, `data` или связь `subject` с ключом."""
        problems = [_describe(err) for err in self._envelope.iter_errors(event)]
        if problems:
            raise EventValidationError(problems)

        problems = _check_time(event["time"])
        topic = self.topics.get(event["type"])
        if event["source"] != topic.producer:
            problems.append(f"source: ожидался {topic.producer!r}, получен {event['source']!r}")
        data = event["data"]
        data_errors = self._data[topic.name].iter_errors(data)
        problems += [_describe(err, prefix="data") for err in data_errors]
        if topic.key in data and data[topic.key] != event["subject"]:
            problems.append(f"subject: должен совпадать с data.{topic.key}")
        if problems:
            raise EventValidationError(problems)


def _describe(err: Any, prefix: str = "") -> str:
    path = ".".join([prefix, *(str(part) for part in err.absolute_path)]).strip(".")
    return f"{path or '<корень>'}: {err.message}"


def _check_time(value: str) -> list[str]:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return [f"time: {value!r} не является датой ISO 8601"]
    if parsed.tzinfo is None:
        return ["time: нужен часовой пояс"]
    return []
