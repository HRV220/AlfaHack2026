"""Контракт транзакционного outbox (архитектура, раздел 9). Реализация — E02-04."""

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class OutboxRecord(BaseModel):
    id: str
    topic: str
    key: str
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None = None
    attempts: int = 0


class OutboxWriter(Protocol):
    async def emit(self, session: Any, topic: str, key: str, payload: dict[str, Any]) -> None:
        """Пишет событие в той же транзакции, что и изменение: откат транзакции убирает событие."""
        ...


class OutboxReader(Protocol):
    async def fetch_unpublished(self, limit: int) -> list[OutboxRecord]:
        """Выбирает пачку неопубликованных записей (`FOR UPDATE SKIP LOCKED`) для релея."""
        ...

    async def mark_published(self, record_id: str) -> None: ...
