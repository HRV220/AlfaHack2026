"""Запуск режимов `relay` и `consumer` (E02-04): БД своей схемы, брокер, остановка по сигналу."""

import asyncio
import importlib
import signal
import sys

import structlog
from sqlalchemy.ext.asyncio import create_async_engine

from cabinet_common.consumer import EventConsumer, Handler, make_consumer
from cabinet_common.db.schemas import service_url
from cabinet_common.events import EventValidator
from cabinet_common.relay import OutboxRelay, make_producer
from cabinet_common.settings import BaseServiceSettings, ServiceMode

SERVICE_SCHEMAS = {
    "core-api": "core",
    "ml-service": "ml",
    "doc-service": "docs",
    "bank-sim": "bank",
}

log = structlog.get_logger()


def schema_for(service_name: str) -> str:
    try:
        return SERVICE_SCHEMAS[service_name]
    except KeyError:
        raise ValueError(f"для сервиса {service_name!r} не задана схема БД") from None


def load_handlers(spec: str | None) -> dict[str, Handler]:
    """`EVENT_HANDLERS=пакет.модуль:ИМЯ` — словарь «топик → обработчик»; не задано — пусто."""
    if not spec:
        return {}
    module_name, _, attr = spec.partition(":")
    if not attr:
        raise ValueError(f"EVENT_HANDLERS должен иметь вид 'модуль:имя', получено {spec!r}")
    handlers: dict[str, Handler] = getattr(importlib.import_module(module_name), attr)
    return handlers


def _stop_event(loop: asyncio.AbstractEventLoop) -> asyncio.Event:
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    return stop


async def _run(settings: BaseServiceSettings) -> None:
    stop = _stop_event(asyncio.get_running_loop())
    relay_mode = settings.service_mode is ServiceMode.RELAY
    handlers = {} if relay_mode else load_handlers(settings.event_handlers)
    if not relay_mode and not handlers:
        # Бизнес-обработчиков ещё нет (подключаются в E04+): БД и брокер не нужны.
        log.info("worker_started", mode="consumer", service=settings.service_name, handlers=0)
        await stop.wait()
        log.info("worker_stopped", mode="consumer")
        return

    engine = create_async_engine(service_url(schema_for(settings.service_name)))
    try:
        if relay_mode:
            log.info("worker_started", mode="relay", service=settings.service_name)
            relay = OutboxRelay(engine, make_producer(settings.kafka_bootstrap_servers))
            await relay.run(stop)
        else:
            log.info(
                "worker_started",
                mode="consumer",
                service=settings.service_name,
                topics=sorted(handlers),
            )
            consumer = EventConsumer(
                engine=engine,
                producer=make_producer(settings.kafka_bootstrap_servers),
                validator=EventValidator(),
                handlers=handlers,
            )
            await consumer.run(
                make_consumer(settings.kafka_bootstrap_servers, settings.service_name), stop
            )
    finally:
        await engine.dispose()
        log.info("worker_stopped", mode=settings.service_mode.value)


def run_worker(settings: BaseServiceSettings) -> None:
    # Psycopg 3 не работает на ProactorEventLoop (Windows, локальный запуск без Docker).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_run(settings), loop_factory=loop_factory)
