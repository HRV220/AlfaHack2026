"""Точка входа образа: режим из SERVICE_MODE (api | consumer | relay), арх. раздел 21."""

import os
import signal
import sys
import threading
import urllib.request

import structlog

from cabinet_common.logging import configure_logging
from cabinet_common.settings import BaseServiceSettings, ServiceMode


def run_idle(mode: ServiceMode) -> None:
    """Заглушка consumer/relay до E02-04: логирует запуск и ждёт сигнала остановки."""
    log = structlog.get_logger()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    log.info("worker_started", mode=mode.value, stub=True)
    stop.wait()
    log.info("worker_stopped", mode=mode.value)


def healthcheck(port: int) -> int:
    """HEALTHCHECK образа: в режиме api опрашивает /health, в остальных режимах всегда успех."""
    if BaseServiceSettings().service_mode is not ServiceMode.API:
        return 0
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as resp:
            return 0 if resp.status == 200 else 1
    except OSError:
        return 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    port = int(os.environ.get("PORT", "8000"))
    if args == ["--healthcheck"]:
        return healthcheck(port)

    settings = BaseServiceSettings()
    configure_logging(settings.log_level)
    if settings.service_mode is ServiceMode.API:
        app_module = os.environ["APP_MODULE"]
        host = "0.0.0.0"  # noqa: S104 - в контейнере нужен внешний интерфейс
        cmd = ["uvicorn", app_module, "--host", host, "--port", str(port)]
        os.execvp(cmd[0], cmd)  # noqa: S606
        return 0
    run_idle(settings.service_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
