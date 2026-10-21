"""Регистрация схем событий в Schema Registry Redpanda: subject `<топик>-value`, BACKWARD."""

import json
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from cabinet_common.events.topics import TopicRegistry, TopicSpec

COMPATIBILITY = "BACKWARD"
DOMAIN_FILE = "schemas/domain.schema.json"
DOMAIN_REF_PREFIX = "../schemas/domain.schema.json#/$defs/"
CONTENT_TYPE = "application/vnd.schemaregistry.v1+json"


class SchemaRegistryError(Exception):
    """Schema Registry недоступен или отклонил схему."""


class SchemaStatus(StrEnum):
    REGISTERED = "registered"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class SchemaResult:
    subject: str
    status: SchemaStatus
    schema_id: int


def _inline_domain_refs(node: Any) -> Any:
    """Заменяет ссылки на `domain.schema.json#/$defs/X` внутренними `#/$defs/X`."""
    if isinstance(node, dict):
        return {
            key: (
                "#/$defs/" + value.removeprefix(DOMAIN_REF_PREFIX)
                if key == "$ref" and isinstance(value, str) and value.startswith(DOMAIN_REF_PREFIX)
                else _inline_domain_refs(value)
            )
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_inline_domain_refs(item) for item in node]
    return node


def build_subject_schema(contracts_dir: Path, topic: TopicSpec) -> dict[str, Any]:
    """Схема сообщения топика: конверт, где `data` заменено схемой топика, `type` — константа.

    Это один самодостаточный документ: ссылки на доменные типы встроены в `$defs`.
    """
    events_dir = contracts_dir / "events"
    schema: dict[str, Any] = json.loads((events_dir / "envelope.schema.json").read_text("utf-8"))
    data: dict[str, Any] = json.loads((events_dir / topic.schema_file).read_text("utf-8"))
    domain: dict[str, Any] = json.loads((contracts_dir / DOMAIN_FILE).read_text("utf-8"))

    for meta in ("$id", "$schema"):
        data.pop(meta, None)
    schema.pop("$id", None)
    schema["title"] = f"Событие {topic.name}"
    schema["properties"] = deepcopy(schema["properties"])
    schema["properties"]["type"] = {"const": topic.name, "type": "string"}
    schema["properties"]["data"] = _inline_domain_refs(data)
    schema["$defs"] = deepcopy(domain.get("$defs", {}))
    return schema


class SchemaRegistryClient:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        # Запросов мало (инициализация), а Redpanda рвёт простаивающие keep-alive соединения:
        # без повторного использования соединений «Server disconnected» не возникает.
        self._http = httpx.Client(
            base_url=url.rstrip("/"),
            timeout=timeout,
            headers={"Content-Type": CONTENT_TYPE},
            limits=httpx.Limits(max_keepalive_connections=0),
        )

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            response = self._http.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise SchemaRegistryError(f"{method} {path}: {exc}") from exc
        if response.status_code >= 400:
            raise SchemaRegistryError(f"{method} {path}: {response.status_code} {response.text}")
        return response.json()

    def subjects(self) -> list[str]:
        result: list[str] = self._request("GET", "/subjects")
        return result

    def register(self, subject: str, schema: dict[str, Any]) -> SchemaResult:
        """Выставляет BACKWARD и регистрирует схему; такая же схема повторно — без изменений."""
        self._request("PUT", f"/config/{subject}", {"compatibility": COMPATIBILITY})
        payload = {"schemaType": "JSON", "schema": json.dumps(schema, sort_keys=True)}
        known = self._lookup(subject, payload)
        if known is not None:
            return SchemaResult(subject, SchemaStatus.UNCHANGED, known)
        created = self._request("POST", f"/subjects/{subject}/versions", payload)
        return SchemaResult(subject, SchemaStatus.REGISTERED, int(created["id"]))

    def _lookup(self, subject: str, payload: dict[str, Any]) -> int | None:
        try:
            response = self._http.post(f"/subjects/{subject}", json=payload)
        except httpx.HTTPError as exc:
            raise SchemaRegistryError(f"POST /subjects/{subject}: {exc}") from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise SchemaRegistryError(
                f"POST /subjects/{subject}: {response.status_code} {response.text}"
            )
        return int(response.json()["id"])


def register_all(url: str, contracts_dir: Path, registry: TopicRegistry) -> list[SchemaResult]:
    """Регистрирует схемы всех топиков; повторный запуск ничего не меняет."""
    client = SchemaRegistryClient(url)
    try:
        return [
            client.register(topic.subject, build_subject_schema(contracts_dir, topic))
            for topic in registry.topics
        ]
    finally:
        client.close()
