"""Контракт идемпотентности: `processed_events(event_id)` (арх. 9). Реализация — E02-04."""

from typing import Any, Protocol


class ProcessedEvents(Protocol):
    async def claim(self, session: Any, event_id: str) -> bool:
        """Фиксирует `event_id` в транзакции обработки; False, если событие уже обработано."""
        ...
