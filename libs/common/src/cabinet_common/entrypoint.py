"""Точка входа образа: режим из SERVICE_MODE (api | consumer | relay), арх. раздел 21.

Режимы consumer и relay запускает `cabinet_common.worker` (E02-04).
"""

import os
import sys
import urllib.request

from cabinet_common.logging import configure_logging
from cabinet_common.settings import BaseServiceSettings, ServiceMode
from cabinet_common.worker import run_worker


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
    run_worker(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
