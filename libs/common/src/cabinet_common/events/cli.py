"""Команда `python -m cabinet_common.events.cli {topics|schemas|all}`: топики и схемы из контракта.

Адреса — из `KAFKA_BOOTSTRAP_SERVERS` и `SCHEMA_REGISTRY_URL`; повторный запуск безопасен.
"""

import argparse
import logging
import sys

import structlog

from cabinet_common.events.admin import ensure_topics
from cabinet_common.events.registry import register_all
from cabinet_common.events.topics import find_contracts_dir, load_topics
from cabinet_common.logging import configure_logging
from cabinet_common.settings import BaseServiceSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cabinet_common.events.cli")
    parser.add_argument("step", choices=["topics", "schemas", "all"])
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    settings = BaseServiceSettings()
    configure_logging(settings.log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # запросы к Registry не нужны в логе
    log = structlog.get_logger()
    contracts_dir = find_contracts_dir()
    registry = load_topics(contracts_dir)

    if args.step in ("topics", "all"):
        topics = ensure_topics(settings.kafka_bootstrap_servers, registry)
        log.info("topics_ready", created=len(topics.created), existing=len(topics.existing))
    if args.step in ("schemas", "all"):
        schemas = register_all(settings.schema_registry_url, contracts_dir, registry)
        for item in schemas:
            log.info("schema_ready", subject=item.subject, status=item.status, id=item.schema_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
