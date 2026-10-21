"""Сборка конверта события (`envelope.schema.json`)."""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from cabinet_common.events.topics import TopicSpec
from cabinet_common.logging import correlation_id as correlation_id_var

CORRELATION_ID = re.compile(r"[0-9a-f]{32}")


def build_envelope(
    topic: TopicSpec,
    key: str,
    data: dict[str, Any],
    *,
    event_id: UUID | None = None,
    time: datetime | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Конверт для `topic`: `correlation_id` берётся из контекста запроса, иначе создаётся новый.

    Значение из контекста используется, только если оно в формате контракта (32 hex-символа).
    """
    context_id = correlation_id_var.get()
    if context_id is not None and not CORRELATION_ID.fullmatch(context_id):
        context_id = None
    return {
        "event_id": str(event_id or uuid4()),
        "type": topic.name,
        "source": topic.producer,
        "time": (time or datetime.now(UTC)).isoformat(),
        "subject": key,
        "schema_version": topic.schema_version,
        "correlation_id": correlation_id or context_id or uuid4().hex,
        "data": data,
    }
