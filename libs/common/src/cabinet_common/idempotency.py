"""Идемпотентность потребителя: `processed_events(event_id)` (архитектура, раздел 9)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CLAIM_EVENT = text(
    "INSERT INTO processed_events (event_id, topic) VALUES (CAST(:event_id AS uuid), :topic) "
    "ON CONFLICT (event_id) DO NOTHING"
)


async def claim(session: AsyncSession, event_id: str, topic: str) -> bool:
    """Фиксирует `event_id` в транзакции обработки; False, если событие уже обработано.

    Откат транзакции снимает отметку, поэтому упавшая обработка может быть повторена.
    """
    result = await session.execute(CLAIM_EVENT, {"event_id": event_id, "topic": topic})
    return bool(result.rowcount == 1)  # type: ignore[attr-defined]
