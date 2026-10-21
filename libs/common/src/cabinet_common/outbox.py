"""Транзакционный outbox (архитектура, раздел 9): событие пишется вместе с изменением данных."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cabinet_common.events import EventValidator, build_envelope


class OutboxRecord(BaseModel):
    id: str
    topic: str
    key: str
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None = None
    attempts: int = 0


INSERT_OUTBOX = text(
    "INSERT INTO outbox (id, topic, key, payload) "
    "VALUES (CAST(:id AS uuid), :topic, :key, CAST(:payload AS jsonb))"
)


class OutboxWriter:
    def __init__(self, validator: EventValidator) -> None:
        self._validator = validator

    async def emit(
        self, session: AsyncSession, topic: str, key: str, payload: dict[str, Any]
    ) -> str:
        """Кладёт событие в `outbox` в транзакции `session`; откат транзакции убирает и событие.

        `payload` — это `data` события; конверт собирается здесь и проверяется до записи.
        Возвращает `event_id` (он же `outbox.id`).
        """
        event = build_envelope(self._validator.topics.get(topic), key, payload)
        self._validator.validate(event)
        await session.execute(
            INSERT_OUTBOX,
            {
                "id": event["event_id"],
                "topic": topic,
                "key": key,
                "payload": json.dumps(event, ensure_ascii=False),
            },
        )
        return str(event["event_id"])
