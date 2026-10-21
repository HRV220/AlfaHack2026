"""Потребитель событий (`SERVICE_MODE=consumer`, E02-04.6, E02-04.7).

Обработка идемпотентна: `event_id` фиксируется в `processed_events` в той же транзакции, что и
обработчик. Ошибка обработчика откатывает транзакцию; после основной попытки и повторов с паузами
из `topics.yaml` сообщение уходит в `<топик>.dlq` без изменений, причина — в заголовках.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

import structlog
from confluent_kafka import Consumer, Producer
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from cabinet_common.events import EventValidationError, EventValidator
from cabinet_common.idempotency import claim
from cabinet_common.logging import correlation_id

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]
Sleep = Callable[[float], Awaitable[None]]

log = structlog.get_logger()


class Outcome(StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    DEAD_LETTERED = "dead_lettered"


class EventConsumer:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        producer: Producer,
        validator: EventValidator,
        handlers: dict[str, Handler],
        sleep: Sleep = asyncio.sleep,
        flush_timeout: float = 10.0,
    ) -> None:
        unknown = set(handlers) - set(validator.topics.names())
        if unknown:
            raise ValueError(f"обработчики для неизвестных топиков: {sorted(unknown)}")
        self._engine = engine
        self._producer = producer
        self._validator = validator
        self._handlers = handlers
        self._sleep = sleep
        self._flush_timeout = flush_timeout

    @property
    def topics(self) -> list[str]:
        return list(self._handlers)

    async def process(self, topic: str, key: bytes | None, value: bytes) -> Outcome:
        """Обрабатывает одно сообщение; возвращается после фиксации результата (в т. ч. в DLQ)."""
        try:
            event = self._parse(topic, value)
        except EventValidationError as exc:
            # Невалидное сообщение повтором не исправить: сразу в DLQ.
            await self._dead_letter(topic, key, value, f"invalid event: {exc}", attempts=0)
            return Outcome.DEAD_LETTERED

        token = correlation_id.set(event["correlation_id"])
        try:
            return await self._process_valid(topic, key, value, event)
        finally:
            correlation_id.reset(token)

    def _parse(self, topic: str, value: bytes) -> dict[str, Any]:
        try:
            event = json.loads(value)
        except ValueError as exc:
            raise EventValidationError([f"сообщение не является JSON: {exc}"]) from exc
        if not isinstance(event, dict):
            raise EventValidationError(["сообщение должно быть объектом"])
        self._validator.validate(event)
        if event["type"] != topic:
            raise EventValidationError(
                [f"type: {event['type']!r} не совпадает с топиком {topic!r}"]
            )
        return event

    async def _process_valid(
        self, topic: str, key: bytes | None, value: bytes, event: dict[str, Any]
    ) -> Outcome:
        pauses = self._validator.topics.defaults.retry_backoff_seconds
        last_error = ""
        for attempt in range(len(pauses) + 1):
            try:
                async with AsyncSession(self._engine) as session, session.begin():
                    if not await claim(session, event["event_id"], topic):
                        log.info("event_duplicate", event_id=event["event_id"], topic=topic)
                        return Outcome.DUPLICATE
                    await self._handlers[topic](session, event)
                log.info("event_processed", event_id=event["event_id"], topic=topic)
                return Outcome.PROCESSED
            except (OperationalError, InterfaceError):
                # Сбой БД, а не сообщения: в DLQ не уходим, смещение не фиксируем — после
                # перезапуска воркера сообщение будет прочитано снова.
                log.error("event_infrastructure_error", event_id=event["event_id"], topic=topic)
                raise
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning(
                    "event_attempt_failed",
                    event_id=event["event_id"],
                    topic=topic,
                    attempt=attempt + 1,
                    error=last_error,
                )
                if attempt < len(pauses):
                    await self._sleep(pauses[attempt])
        await self._dead_letter(topic, key, value, last_error, attempts=len(pauses) + 1)
        return Outcome.DEAD_LETTERED

    async def _dead_letter(
        self, topic: str, key: bytes | None, value: bytes, reason: str, *, attempts: int
    ) -> None:
        dlq = self._validator.topics.get(topic).dlq_name
        self._producer.produce(
            dlq,
            key=key,
            value=value,
            headers=[
                ("dlq.reason", reason.encode()),
                ("dlq.attempts", str(attempts).encode()),
                ("dlq.original_topic", topic.encode()),
            ],
        )
        remaining = await asyncio.to_thread(self._producer.flush, self._flush_timeout)
        if remaining:
            raise RuntimeError(f"не удалось записать сообщение в {dlq}")
        log.error("event_dead_lettered", topic=topic, dlq=dlq, reason=reason, attempts=attempts)

    async def run(self, consumer: Consumer, stop: asyncio.Event) -> None:
        """Читает топики обработчиков; смещение фиксируется после обработки или записи в DLQ."""
        consumer.subscribe(self.topics)
        try:
            while not stop.is_set():
                msg = await asyncio.to_thread(consumer.poll, 1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.warning("consumer_error", error=str(msg.error()))
                    continue
                await self.process(str(msg.topic()), msg.key(), msg.value() or b"")
                await asyncio.to_thread(consumer.commit, message=msg, asynchronous=False)
        finally:
            consumer.close()


def make_consumer(bootstrap_servers: str, group_id: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
