import logging

from cabinet_common.init.runner import run_steps
from cabinet_common.init.steps import InitSettings, default_steps
from cabinet_common.logging import configure_logging


def main() -> int:
    settings = InitSettings()
    configure_logging(settings.log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # запросы к Registry и MLflow — шум
    return run_steps(default_steps(settings))


if __name__ == "__main__":
    raise SystemExit(main())
