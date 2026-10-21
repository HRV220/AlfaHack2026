"""Выполнение шагов init по порядку: лог начала и итога каждого шага, код выхода (E02-06.2)."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import structlog

log = structlog.get_logger()


class StepWarning(Exception):
    """Шаг не выполнен полностью, но init продолжается (например, LLM ещё не готова)."""


@dataclass(frozen=True)
class Step:
    """Шаг init: `run` возвращает короткое описание результата для лога.

    Ошибка обязательного шага останавливает init (код 1); необязательного — только предупреждение.
    """

    name: str
    run: Callable[[], str]
    required: bool = True


def run_steps(steps: Sequence[Step]) -> int:
    """0 — все обязательные шаги выполнены; 1 — обязательный шаг упал (остальные не запускаются)."""
    started = time.monotonic()
    warnings = 0
    for step in steps:
        log.info("init_step_started", step=step.name)
        step_started = time.monotonic()
        try:
            detail = step.run()
        except StepWarning as warning:
            if step.required:
                # Предупреждение допустимо только у необязательного шага: иначе init
                # продолжил бы работу на непрошедшем миграции или seed.
                log.error("init_step_failed", step=step.name, error=f"StepWarning: {warning}")
                return 1
            warnings += 1
            log.warning("init_step_warning", step=step.name, detail=str(warning))
            continue
        except Exception as exc:
            seconds = round(time.monotonic() - step_started, 1)
            if step.required:
                log.error("init_step_failed", step=step.name, seconds=seconds, error=repr(exc))
                return 1
            warnings += 1
            log.warning("init_step_skipped", step=step.name, seconds=seconds, error=repr(exc))
            continue
        log.info(
            "init_step_done",
            step=step.name,
            seconds=round(time.monotonic() - step_started, 1),
            detail=detail,
        )
    log.info(
        "init_done",
        steps=len(steps),
        warnings=warnings,
        seconds=round(time.monotonic() - started, 1),
    )
    return 0
