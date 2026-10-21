"""Проверка лимитов памяти профиля core (E02-02.8, NFR-01, NFR-22).

У каждого контейнера должен быть `mem_limit`; сумма по постоянно работающим контейнерам (с
`restart` не "no"), включая локальную LLM, не превышает бюджета (по умолчанию 14 ГиБ).

    python deploy/compose/check_limits.py            # проверка (код 1 при нарушении)
    python deploy/compose/check_limits.py --table    # таблица Markdown для README
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy" / "compose" / "compose.yaml"
GIB = 1024**3
MIB = 1024**2


def load_config() -> dict[str, Any]:
    cmd = ["docker", "compose", "--project-directory", str(ROOT), "-f", str(COMPOSE)]
    out = subprocess.run(  # noqa: S603
        [*cmd, "--profile", "core", "config", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    config: dict[str, Any] = json.loads(out.stdout)
    return config


def limits(config: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    """Лимиты в байтах по сервисам и список сервисов без `mem_limit`."""
    result: dict[str, int] = {}
    missing: list[str] = []
    for name, service in config["services"].items():
        value = service.get("mem_limit")
        if value is None:
            missing.append(name)
        else:
            result[name] = int(value)
    return result, missing


def resident(config: dict[str, Any]) -> list[str]:
    """Постоянно работающие сервисы: разовые (`restart: "no"`) в сумму не входят."""
    return [n for n, s in config["services"].items() if s.get("restart") != "no"]


def check(config: dict[str, Any], budget_bytes: int) -> list[str]:
    """Нарушения: контейнеры без лимита и превышение бюджета. Пустой список — всё в порядке."""
    by_service, missing = limits(config)
    problems = [f"нет mem_limit: {name}" for name in missing]
    total = sum(by_service[name] for name in resident(config) if name in by_service)
    if total > budget_bytes:
        problems.append(
            f"сумма лимитов {total / GIB:.2f} ГиБ больше бюджета {budget_bytes / GIB:.0f} ГиБ"
        )
    return problems


def table(config: dict[str, Any]) -> str:
    by_service, _ = limits(config)
    always = set(resident(config))
    rows = ["| Контейнер | Лимит, МиБ | Работает постоянно |", "| --- | ---: | :---: |"]
    for name, value in by_service.items():
        rows.append(f"| {name} | {value // MIB} | {'да' if name in always else 'нет (разовый)'} |")
    total = sum(v for n, v in by_service.items() if n in always)
    rows.append(f"| **Итого (постоянные)** | **{total // MIB}** ({total / GIB:.2f} ГиБ) | |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--budget-gib", type=float, default=14.0)
    parser.add_argument("--table", action="store_true")
    args = parser.parse_args(argv)
    config = load_config()
    if args.table:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        print(table(config))
        return 0
    problems = check(config, int(args.budget_gib * GIB))
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
