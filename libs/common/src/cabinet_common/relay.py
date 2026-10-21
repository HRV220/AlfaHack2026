"""Релей outbox → брокер (`SERVICE_MODE=relay`, E02-04.5).

Пачка строк блокируется `FOR UPDATE SKIP LOCKED`, поэтому параллельные релеи берут разные
записи и не дублируют публикацию; блокировка держится до фиксации пометки `published_at`.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import structlog
from confluent_kafka import Producer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

SELECT_BATCH = text(
    "SELECT id::text AS id, topic, key, payload FROM outbox "
    "WHERE published_at IS NULL ORDER BY created_at LIMIT :limit FOR UPDATE SKIP LOCKED"
)
MARK_PUBLISHED = text(
    "UPDATE outbox SET published_at = now(), attempts = attempts + 1 "
    "WHERE id = ANY(CAST(:ids AS uuid[]))"
)
MARK_FAILED = text("UPDATE outbox SET attempts = attempts + 1 WHERE id = ANY(CAST(:ids AS uuid[]))")

log = structlog.get_logger()


def make_producer(bootstrap_servers: str) -> Producer:
    """Продюсер с `acks=all` и идемпотентной отправкой (без дублей при повторе внутри сессии)."""
    return Producer(
        {
            "bootstrap.servers": bootstrap_servers,
            "acks": "all",
            "enable.idempotence": True,
            "linger.ms": 5,
        }
    )


class OutboxRelay:
    def __init__(
        self,
        engine: AsyncEngine,
        producer: Producer,
        *,
        batch_size: int = 100,
        flush_timeout: float = 10.0,
    ) -> None:
        self._engine = engine
        self._producer = producer
        self._batch_size = batch_size
        self._flush_timeout = flush_timeout

    async def publish_batch(self) -> int:
        """Публикует одну пачку; возвращает число подтверждённых брокером записей."""
        async with self._engine.begin() as conn:
            rows = (await conn.execute(SELECT_BATCH, {"limit": self._batch_size})).mappings().all()
            if not rows:
                return 0

            delivered: set[str] = set()
            errors: dict[str, str] = {}

            def on_delivery(record_id: str) -> Callable[[Any, Any], None]:
                def callback(err: Any, _msg: Any) -> None:
                    if err is None:
                        delivered.add(record_id)
                    else:
                        errors[record_id] = str(err)

                return callback

            for row in rows:
                payload = row["payload"]
                self._producer.produce(
                    row["topic"],
                    key=row["key"].encode(),
                    value=json.dumps(payload, ensure_ascii=False).encode(),
                    on_delivery=on_delivery(row["id"]),
                )
            remaining = await asyncio.to_thread(self._producer.flush, self._flush_timeout)
            if remaining:
                # Недоставленное убираем из очереди продюсера, иначе оно уйдёт позже и дублируется
                # повтором следующей пачки (и нарушит порядок внутри ключа).
                self._producer.purge()
                await asyncio.to_thread(self._producer.flush, 1.0)

            failed = [row["id"] for row in rows if row["id"] not in delivered]
            if delivered:
                await conn.execute(MARK_PUBLISHED, {"ids": sorted(delivered)})
            if failed:
                await conn.execute(MARK_FAILED, {"ids": failed})
                log.warning("outbox_publish_failed", count=len(failed), errors=errors)
            for row in rows:
                if row["id"] in delivered:
                    log.info(
                        "outbox_published",
                        event_id=row["id"],
                        topic=row["topic"],
                        correlation_id=row["payload"].get("correlation_id"),
                    )
            return len(delivered)

    async def run(self, stop: asyncio.Event, poll_interval: float = 0.5) -> None:
        """Опрашивает outbox до сигнала остановки; ошибка пачки не завершает цикл."""
        while not stop.is_set():
            try:
                published = await self.publish_batch()
            except Exception:
                log.exception("outbox_batch_error")
                published = 0
            if published == 0:
                try:
                    await asyncio.wait_for(stop.wait(), poll_interval)
                except TimeoutError:
                    pass
