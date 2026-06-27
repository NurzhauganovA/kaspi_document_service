import uuid
from datetime import (
    datetime,
    timezone,
)
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import (
    OutboxEvent,
    OutboxStatus,
)


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(
        self,
        aggregate_id: uuid.UUID,
        topic: str,
        key: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        event = OutboxEvent(
            aggregate_id=aggregate_id,
            topic=topic,
            key=key,
            payload=payload,
            status=OutboxStatus.PENDING,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def fetch_pending(self, limit: int = 50) -> list[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_published(self, event: OutboxEvent) -> None:
        event.status = OutboxStatus.PUBLISHED
        event.published_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def mark_failed(self, event: OutboxEvent) -> None:
        event.retry_count += 1
        if event.retry_count >= 5:
            event.status = OutboxStatus.FAILED
        await self._session.flush()
