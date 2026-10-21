"""Шаги init по порядку (E02-06.2): ожидание → расширения и роли → миграции → топики и схемы →
seed → MLflow → LLM. Бакеты MinIO создаёт `minio-init`, БД MLflow — `mlflow-db-init` (Compose)."""

import asyncio
import socket
import sys
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import create_async_engine

from cabinet_common.db.bootstrap import bootstrap
from cabinet_common.db.migrate import upgrade_all
from cabinet_common.db.schemas import SPECS, admin_url, service_url
from cabinet_common.events.admin import ensure_topics
from cabinet_common.events.registry import SchemaStatus, register_all
from cabinet_common.events.topics import find_contracts_dir, load_topics
from cabinet_common.init.runner import Step, StepWarning
from cabinet_common.init.seed import load_cards, upsert_cards
from cabinet_common.settings import BaseServiceSettings


class InitSettings(BaseServiceSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    mlflow_tracking_uri: str = "http://mlflow:5000"
    ollama_url: str = "http://ollama:11434"
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    assistant_enabled: bool = True
    models_dir: Path | None = None
    wait_timeout_sec: float = 120.0


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Запускает корутину; на Windows psycopg требует SelectorEventLoop."""
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=factory) as runner:
        return runner.run(coro)


def wait_tcp(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=3):
                return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"{host}:{port} недоступен за {timeout:.0f} с ({exc})") from exc
            time.sleep(1)


def wait_http(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            if httpx.get(url, timeout=3).status_code < 500:
                return
            error = "ответ 5xx"
        except httpx.HTTPError as exc:
            error = str(exc)
        if time.monotonic() >= deadline:
            raise TimeoutError(f"{url} недоступен за {timeout:.0f} с ({error})")
        time.sleep(1)


def parse_broker(bootstrap_servers: str, default_port: int = 9092) -> tuple[str, int]:
    """Хост и порт первого брокера из `host:port[,host:port]`; без схемы `PLAINTEXT://`."""
    first = bootstrap_servers.split(",")[0].strip().rpartition("://")[2]
    host, sep, port = first.rpartition(":")
    if not sep:
        return first, default_port
    if not host or not port.isdigit():
        raise ValueError(f"не удалось разобрать адрес брокера {bootstrap_servers!r}")
    return host, int(port)


def wait_step(settings: InitSettings) -> str:
    kafka_host, kafka_port = parse_broker(settings.kafka_bootstrap_servers)
    wait_tcp(settings.postgres_host, settings.postgres_port, settings.wait_timeout_sec)
    wait_tcp(kafka_host, kafka_port, settings.wait_timeout_sec)
    wait_http(f"{settings.schema_registry_url.rstrip('/')}/subjects", settings.wait_timeout_sec)
    return "PostgreSQL, Redpanda и Schema Registry доступны"


def bootstrap_step() -> str:
    bootstrap(admin_url())
    return "расширения и роли схем готовы"


def migrations_step() -> str:
    upgrade_all()
    return f"миграции применены: {', '.join(SPECS)}"


def topics_step(settings: InitSettings) -> str:
    result = ensure_topics(settings.kafka_bootstrap_servers, load_topics(find_contracts_dir()))
    return f"топики: создано {len(result.created)}, уже были {len(result.existing)}"


def schemas_step(settings: InitSettings) -> str:
    contracts = find_contracts_dir()
    results = register_all(settings.schema_registry_url, contracts, load_topics(contracts))
    new = sum(item.status is SchemaStatus.REGISTERED for item in results)
    return f"схемы: зарегистрировано {new}, без изменений {len(results) - new}"


def seed_step() -> str:
    async def seed() -> str:
        engine = create_async_engine(service_url("core"))
        try:
            return (await upsert_cards(engine, load_cards())).describe()
        finally:
            await engine.dispose()

    return _run(seed())


def mlflow_step(settings: InitSettings) -> str:
    base = settings.mlflow_tracking_uri.rstrip("/")
    try:
        httpx.get(f"{base}/health", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        raise StepWarning(f"MLflow недоступен ({exc}): регистрация моделей пропущена") from exc
    artifacts = list(settings.models_dir.glob("*/MLmodel")) if settings.models_dir else []
    if not artifacts:
        raise StepWarning(
            "MLflow доступен, артефактов моделей нет: алиас champion не назначен (обучение — E07)"
        )
    return f"MLflow доступен, найдено артефактов моделей: {len(artifacts)}"


def llm_step(settings: InitSettings) -> str:
    if not settings.assistant_enabled:
        return "ассистент выключен (ASSISTANT_ENABLED=false), проверка LLM пропущена"
    try:
        response = httpx.get(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise StepWarning(f"Ollama недоступна ({exc}): подбор пойдёт через форму (РШ-9)") from exc
    names = {model["name"] for model in response.json().get("models", [])}
    if settings.llm_model not in names:
        raise StepWarning(
            f"модель {settings.llm_model} не загружена в Ollama (загрузка — E02-07): "
            "подбор пойдёт через форму (РШ-9)"
        )
    return f"LLM готова: {settings.llm_model}"


def default_steps(settings: InitSettings) -> list[Step]:
    return [
        Step("wait", lambda: wait_step(settings)),
        Step("bootstrap", bootstrap_step),
        Step("migrations", migrations_step),
        Step("topics", lambda: topics_step(settings)),
        Step("schemas", lambda: schemas_step(settings)),
        Step("seed", seed_step),
        Step("mlflow", lambda: mlflow_step(settings), required=False),
        Step("llm", lambda: llm_step(settings), required=False),
    ]
