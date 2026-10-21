"""Outbox → Redpanda → consumer на настоящих PostgreSQL и Redpanda (E02-04.4–E02-04.9).

Нужны оба хранилища: `make events-test` поднимает их сам (`TEST_PG_*`, `KAFKA_BOOTSTRAP_SERVERS`).
"""

import asyncio
import json
import os
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import psycopg
import pytest
from cabinet_common.consumer import EventConsumer, Outcome, make_consumer
from cabinet_common.db.bootstrap import bootstrap
from cabinet_common.db.migrate import upgrade_all
from cabinet_common.db.schemas import admin_url, service_url
from cabinet_common.events import (
    EventValidationError,
    EventValidator,
    build_envelope,
    find_contracts_dir,
)
from cabinet_common.events.admin import ensure_topics
from cabinet_common.logging import correlation_id
from cabinet_common.outbox import ForeignTopicError, OutboxWriter
from cabinet_common.relay import OutboxRelay, make_producer
from confluent_kafka import Consumer, KafkaError, KafkaException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

pytestmark = pytest.mark.integration

PG = {
    "host": os.environ.get("TEST_PG_HOST", "localhost"),
    "port": int(os.environ.get("TEST_PG_PORT", "55432")),
    "user": os.environ.get("TEST_PG_USER", "postgres"),
    "password": os.environ.get("TEST_PG_PASSWORD", "pg_admin_test"),
}
KAFKA = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:55092")
CONTRACTS = find_contracts_dir()
VALIDATOR = EventValidator(CONTRACTS)


@pytest.fixture(scope="module", autouse=True)
def database() -> Iterator[str]:
    name = f"evt_{uuid.uuid4().hex[:10]}"
    admin = psycopg.connect(dbname="postgres", autocommit=True, **PG)  # type: ignore[arg-type]
    admin.execute(f'CREATE DATABASE "{name}"')
    env = {
        "POSTGRES_HOST": str(PG["host"]),
        "POSTGRES_PORT": str(PG["port"]),
        "POSTGRES_DB": name,
        "POSTGRES_USER": str(PG["user"]),
        "POSTGRES_PASSWORD": str(PG["password"]),
    }
    with pytest.MonkeyPatch.context() as mp:
        for key, value in env.items():
            mp.setenv(key, value)
        bootstrap(admin_url())
        upgrade_all()
        ensure_topics(KAFKA, VALIDATOR.topics)
        yield name
    admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    admin.close()


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(service_url("core"))
    yield eng
    await eng.dispose()


def example_data(topic: str, **changes: Any) -> dict[str, Any]:
    file = CONTRACTS / "examples" / "events" / f"{topic}.example.json"
    data: dict[str, Any] = json.loads(file.read_text("utf-8"))["data"]
    data.update(changes)
    return data


def uploaded(app_id: str | None = None) -> tuple[str, dict[str, Any]]:
    app_id = app_id or str(uuid.uuid4())
    data = example_data("document.uploaded", application_id=app_id, document_id=str(uuid.uuid4()))
    return app_id, data


async def emit_uploaded(engine: AsyncEngine, count: int = 1) -> list[str]:
    writer = OutboxWriter(VALIDATOR, "core-api")
    ids: list[str] = []
    async with AsyncSession(engine) as session, session.begin():
        for _ in range(count):
            app_id, data = uploaded()
            ids.append(await writer.emit(session, "document.uploaded", app_id, data))
    return ids


async def count_rows(engine: AsyncEngine, sql: str, **params: Any) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(text(sql), params)).scalar_one())


def read_topic(topic: str, expected: set[str], timeout: float = 30.0) -> list[Any]:
    """Читает топик новой группой с начала, пока не увидит все `expected` event_id (+ короткий добор)."""
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA,
            "group.id": f"test-{uuid.uuid4().hex}",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([topic])
    found: list[Any] = []
    seen: set[str] = set()
    end = time.monotonic() + timeout
    drain_until: float | None = None
    try:
        while time.monotonic() < end:
            msg = consumer.poll(1.0)
            if drain_until is not None and time.monotonic() > drain_until:
                break
            if msg is None or msg.error():
                continue
            event_id = json.loads(msg.value())["event_id"]
            if event_id in expected:
                found.append(msg)
                seen.add(event_id)
                if seen == expected and drain_until is None:
                    drain_until = time.monotonic() + 2
    finally:
        consumer.close()
    return found


# --- E02-04.4: outbox -------------------------------------------------------------------------


async def test_rollback_leaves_no_event(engine: AsyncEngine) -> None:
    writer = OutboxWriter(VALIDATOR, "core-api")
    app_id, data = uploaded()
    event_id = ""
    with pytest.raises(RuntimeError):
        async with AsyncSession(engine) as session, session.begin():
            event_id = await writer.emit(session, "document.uploaded", app_id, data)
            raise RuntimeError("откат")
    assert (
        await count_rows(
            engine, "SELECT count(*) FROM outbox WHERE id = CAST(:i AS uuid)", i=event_id
        )
        == 0
    )


async def test_commit_stores_valid_envelope(engine: AsyncEngine) -> None:
    (event_id,) = await emit_uploaded(engine)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT id::text, topic, key, payload, published_at FROM outbox WHERE id = CAST(:i AS uuid)"
                ),
                {"i": event_id},
            )
        ).one()
    assert row.id == event_id == row.payload["event_id"]
    assert row.topic == "document.uploaded"
    assert row.key == row.payload["subject"]
    assert row.published_at is None
    VALIDATOR.validate(row.payload)


async def test_invalid_event_is_not_written(engine: AsyncEngine) -> None:
    writer = OutboxWriter(VALIDATOR, "core-api")
    app_id, data = uploaded()
    data["size_bytes"] = 0
    before = await count_rows(engine, "SELECT count(*) FROM outbox")
    with pytest.raises(EventValidationError):
        async with AsyncSession(engine) as session, session.begin():
            await writer.emit(session, "document.uploaded", app_id, data)
    assert await count_rows(engine, "SELECT count(*) FROM outbox") == before


# --- E02-04.5: relay ---------------------------------------------------------------------------


async def test_relay_publishes_and_marks(engine: AsyncEngine) -> None:
    ids = await emit_uploaded(engine, 3)
    relay = OutboxRelay(engine, make_producer(KAFKA))
    published = 0
    while published < 3:
        published += await relay.publish_batch()
    messages = read_topic("document.uploaded", set(ids))
    assert {json.loads(m.value())["event_id"] for m in messages} == set(ids)
    for msg in messages:
        assert msg.key().decode() == json.loads(msg.value())["subject"]
    unpublished = await count_rows(
        engine,
        "SELECT count(*) FROM outbox WHERE id = ANY(CAST(:ids AS uuid[])) AND published_at IS NULL",
        ids=ids,
    )
    assert unpublished == 0


async def test_parallel_relays_do_not_duplicate(engine: AsyncEngine) -> None:
    ids = await emit_uploaded(engine, 20)
    first = OutboxRelay(engine, make_producer(KAFKA), batch_size=10)
    second = OutboxRelay(engine, make_producer(KAFKA), batch_size=10)
    await asyncio.gather(first.publish_batch(), second.publish_batch())
    while await first.publish_batch():
        pass
    messages = read_topic("document.uploaded", set(ids))
    delivered = [json.loads(m.value())["event_id"] for m in messages]
    assert sorted(delivered) == sorted(ids)


async def test_failed_delivery_keeps_record_unpublished(engine: AsyncEngine) -> None:
    (event_id,) = await emit_uploaded(engine)

    class BrokenProducer:
        def __init__(self) -> None:
            self.callbacks: list[Any] = []

        def produce(self, topic: str, key: bytes, value: bytes, on_delivery: Any) -> None:
            self.callbacks.append(on_delivery)

        def flush(self, timeout: float) -> int:
            for callback in self.callbacks:
                callback("брокер недоступен", None)
            return 0

    relay = OutboxRelay(engine, BrokenProducer(), batch_size=1000)  # type: ignore[arg-type]
    assert await relay.publish_batch() == 0
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT published_at, attempts FROM outbox WHERE id = CAST(:i AS uuid)"),
                {"i": event_id},
            )
        ).one()
    assert row.published_at is None
    assert row.attempts == 1


class FakeProducer:
    """Продюсер без брокера: `reject_keys` отклоняются при `produce`, `fail_keys` — при доставке."""

    def __init__(self, reject_keys: set[str] = frozenset(), fail_keys: set[str] = frozenset()):  # type: ignore[assignment]
        self.reject_keys = reject_keys
        self.fail_keys = fail_keys
        self.sent: list[str] = []
        self._pending: list[tuple[str, Any]] = []

    def produce(self, topic: str, key: bytes, value: bytes, on_delivery: Any) -> None:
        if key.decode() in self.reject_keys:
            raise KafkaException(KafkaError(KafkaError.MSG_SIZE_TOO_LARGE))
        self.sent.append(json.loads(value)["event_id"])
        self._pending.append((key.decode(), on_delivery))

    def flush(self, timeout: float) -> int:
        for key, callback in self._pending:
            callback("доставка не удалась" if key in self.fail_keys else None, None)
        self._pending.clear()
        return 0

    def purge(self) -> None:
        self._pending.clear()


async def clear_outbox(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM outbox"))


async def emit_for_keys(engine: AsyncEngine, keys: list[str]) -> list[str]:
    """Событие `document.uploaded` на каждый ключ (повтор ключа — следующее событие того же ключа)."""
    writer = OutboxWriter(VALIDATOR, "core-api")
    ids: list[str] = []
    async with AsyncSession(engine) as session, session.begin():
        for key in keys:
            _, data = uploaded(key)
            ids.append(await writer.emit(session, "document.uploaded", key, data))
    return ids


async def outbox_state(engine: AsyncEngine, event_id: str) -> Any:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT published_at, attempts FROM outbox WHERE id = CAST(:i AS uuid)"),
                {"i": event_id},
            )
        ).one()


async def test_rejected_record_does_not_block_the_batch(engine: AsyncEngine) -> None:
    await clear_outbox(engine)
    keys = [str(uuid.uuid4()) for _ in range(3)]
    bad, *good = await emit_for_keys(engine, keys)
    relay = OutboxRelay(engine, FakeProducer(reject_keys={keys[0]}))  # type: ignore[arg-type]

    assert await relay.publish_batch() == 2

    rejected = await outbox_state(engine, bad)
    assert rejected.published_at is None
    assert rejected.attempts == 1
    for event_id in good:
        assert (await outbox_state(engine, event_id)).published_at is not None


async def test_same_key_events_are_published_in_creation_order(engine: AsyncEngine) -> None:
    await clear_outbox(engine)
    key = str(uuid.uuid4())
    first, second = await emit_for_keys(engine, [key, key])
    relay = OutboxRelay(engine, make_producer(KAFKA))

    assert await relay.publish_batch() == 1, "за проход берётся одна запись на ключ"
    assert (await outbox_state(engine, second)).published_at is None
    assert await relay.publish_batch() == 1

    messages = {
        json.loads(m.value())["event_id"]: m
        for m in read_topic("document.uploaded", {first, second})
    }
    assert messages[first].offset() < messages[second].offset()


async def test_failed_event_holds_back_later_events_of_the_same_key(engine: AsyncEngine) -> None:
    await clear_outbox(engine)
    key = str(uuid.uuid4())
    first, second = await emit_for_keys(engine, [key, key])

    broken = FakeProducer(fail_keys={key})
    assert await OutboxRelay(engine, broken).publish_batch() == 0  # type: ignore[arg-type]
    assert broken.sent == [first], "второе событие ключа не должно обгонять первое"
    assert (await outbox_state(engine, first)).attempts == 1
    assert (await outbox_state(engine, second)).published_at is None

    healthy = FakeProducer()
    relay = OutboxRelay(engine, healthy)  # type: ignore[arg-type]
    await relay.publish_batch()
    await relay.publish_batch()
    assert healthy.sent == [first, second]


async def test_foreign_topic_is_rejected(engine: AsyncEngine) -> None:
    writer = OutboxWriter(VALIDATOR, "core-api")  # decision.made публикует ml-service
    data = example_data("decision.made")
    before = await count_rows(engine, "SELECT count(*) FROM outbox")
    with pytest.raises(ForeignTopicError):
        async with AsyncSession(engine) as session, session.begin():
            await writer.emit(session, "decision.made", data["decision"]["application_id"], data)
    assert await count_rows(engine, "SELECT count(*) FROM outbox") == before


# --- E02-04.6, E02-04.7: consumer, повторы, DLQ -----------------------------------------------


def make_message() -> tuple[bytes, bytes, str]:
    """Сообщение `document.uploaded`: ключ, значение и event_id."""
    app_id, data = uploaded()
    envelope = build_envelope(VALIDATOR.topics.get("document.uploaded"), app_id, data)
    VALIDATOR.validate(envelope)
    return app_id.encode(), json.dumps(envelope).encode(), envelope["event_id"]


class Recorder:
    def __init__(self, fail_times: int = 0) -> None:
        self.calls = 0
        self.fail_times = fail_times

    async def __call__(self, session: AsyncSession, event: dict[str, Any]) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(f"сбой {self.calls}")


def make_consumer_under_test(
    engine: AsyncEngine, handler: Recorder, pauses: list[float]
) -> EventConsumer:
    async def fake_sleep(seconds: float) -> None:
        pauses.append(seconds)

    return EventConsumer(
        engine=engine,
        producer=make_producer(KAFKA),
        validator=VALIDATOR,
        handlers={"document.uploaded": handler},
        sleep=fake_sleep,
    )


async def test_duplicate_delivery_is_processed_once(engine: AsyncEngine) -> None:
    key, value, event_id = make_message()
    handler = Recorder()
    consumer = make_consumer_under_test(engine, handler, [])
    assert await consumer.process("document.uploaded", key, value) is Outcome.PROCESSED
    assert await consumer.process("document.uploaded", key, value) is Outcome.DUPLICATE
    assert handler.calls == 1
    seen = await count_rows(
        engine,
        "SELECT count(*) FROM processed_events WHERE event_id = CAST(:i AS uuid)",
        i=event_id,
    )
    assert seen == 1


async def test_failing_handler_goes_to_dlq_after_four_calls(engine: AsyncEngine) -> None:
    key, value, event_id = make_message()
    handler = Recorder(fail_times=100)
    pauses: list[float] = []
    consumer = make_consumer_under_test(engine, handler, pauses)

    assert await consumer.process("document.uploaded", key, value) is Outcome.DEAD_LETTERED

    assert handler.calls == 4
    assert pauses == [1, 5, 25]
    (msg,) = read_topic("document.uploaded.dlq", {event_id})
    assert msg.value() == value
    headers = {name: val.decode() for name, val in msg.headers()}
    assert headers["dlq.attempts"] == "4"
    assert headers["dlq.original_topic"] == "document.uploaded"
    assert "RuntimeError" in headers["dlq.reason"]
    seen = await count_rows(
        engine,
        "SELECT count(*) FROM processed_events WHERE event_id = CAST(:i AS uuid)",
        i=event_id,
    )
    assert seen == 0, "упавшая обработка не должна оставлять отметку processed_events"


async def test_database_failure_is_not_dead_lettered(engine: AsyncEngine) -> None:
    key, value, event_id = make_message()

    async def broken(session: AsyncSession, event: dict[str, Any]) -> None:
        raise OperationalError("SELECT 1", {}, Exception("соединение потеряно"))

    consumer = EventConsumer(
        engine=engine,
        producer=make_producer(KAFKA),
        validator=VALIDATOR,
        handlers={"document.uploaded": broken},
    )
    with pytest.raises(OperationalError):
        await consumer.process("document.uploaded", key, value)
    seen = await count_rows(
        engine,
        "SELECT count(*) FROM processed_events WHERE event_id = CAST(:i AS uuid)",
        i=event_id,
    )
    assert seen == 0


async def test_handler_recovering_after_retries_is_processed(engine: AsyncEngine) -> None:
    key, value, _ = make_message()
    handler = Recorder(fail_times=2)
    pauses: list[float] = []
    consumer = make_consumer_under_test(engine, handler, pauses)
    assert await consumer.process("document.uploaded", key, value) is Outcome.PROCESSED
    assert handler.calls == 3
    assert pauses == [1, 5]


async def test_invalid_message_goes_straight_to_dlq(engine: AsyncEngine) -> None:
    handler = Recorder()
    consumer = make_consumer_under_test(engine, handler, [])
    marker = uuid.uuid4().hex
    value = json.dumps({"event_id": marker}).encode()
    assert await consumer.process("document.uploaded", b"k", value) is Outcome.DEAD_LETTERED
    assert handler.calls == 0

    reader = Consumer(
        {
            "bootstrap.servers": KAFKA,
            "group.id": f"test-{uuid.uuid4().hex}",
            "auto.offset.reset": "earliest",
        }
    )
    reader.subscribe(["document.uploaded.dlq"])
    try:
        deadline = time.monotonic() + 45  # poll возвращает сразу при ошибке группы: ждём по времени
        while time.monotonic() < deadline:
            msg = reader.poll(1.0)
            if msg is not None and not msg.error() and marker in msg.value().decode():
                headers = {name: val.decode() for name, val in msg.headers()}
                assert headers["dlq.attempts"] == "0"
                assert headers["dlq.reason"].startswith("invalid event")
                return
    finally:
        reader.close()
    pytest.fail("сообщение не найдено в DLQ")


# --- E02-04.8, E02-04.9: сквозной путь и correlation_id ---------------------------------------


async def test_outbox_to_consumer_end_to_end_keeps_correlation_id(engine: AsyncEngine) -> None:
    trace = uuid.uuid4().hex
    writer = OutboxWriter(VALIDATOR, "core-api")
    app_id, uploaded_data = uploaded()
    submitted_data = example_data("application.submitted", application_id=app_id)

    token = correlation_id.set(trace)  # как это сделал бы HTTP-middleware на входе запроса
    try:
        async with AsyncSession(engine) as session, session.begin():
            first = await writer.emit(session, "document.uploaded", app_id, uploaded_data)
            second = await writer.emit(session, "application.submitted", app_id, submitted_data)
    finally:
        correlation_id.reset(token)

    relay = OutboxRelay(engine, make_producer(KAFKA))
    published = 0
    while published < 2:
        published += await relay.publish_batch()

    observed: dict[str, tuple[str, str | None]] = {}
    both_seen = asyncio.Event()

    async def handle(session: AsyncSession, event: dict[str, Any]) -> None:
        if event["event_id"] in (first, second):
            observed[event["event_id"]] = (event["correlation_id"], correlation_id.get())
            if len(observed) == 2:
                both_seen.set()

    consumer = EventConsumer(
        engine=engine,
        producer=make_producer(KAFKA),
        validator=VALIDATOR,
        handlers={"document.uploaded": handle, "application.submitted": handle},
    )
    stop = asyncio.Event()
    runner = asyncio.create_task(
        consumer.run(make_consumer(KAFKA, f"e2e-{uuid.uuid4().hex}"), stop)
    )
    try:
        async with asyncio.timeout(60):
            await both_seen.wait()
    finally:
        stop.set()
        await runner

    assert observed == {first: (trace, trace), second: (trace, trace)}
    processed = await count_rows(
        engine,
        "SELECT count(*) FROM processed_events WHERE event_id = ANY(CAST(:ids AS uuid[]))",
        ids=[first, second],
    )
    assert processed == 2
