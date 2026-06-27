from typing import Any

from app.core.logging import get_logger
from app.db.session import AsyncSessionFactory
from app.repositories.outbox_repository import OutboxRepository
from app.services.kafka_producer import (
    get_kafka_producer,
    is_producer_ready,
)

logger = get_logger(__name__)


class OutboxService:
    async def process_batch(self, batch_size: int = 50) -> int:
        """Relay pending outbox events to Kafka. Returns number of published events."""
        published = 0
        producer = await get_kafka_producer()

        async with AsyncSessionFactory() as session:
            async with session.begin():
                repo = OutboxRepository(session)
                events = await repo.fetch_pending(limit=batch_size)

                for event in events:
                    try:
                        await producer.publish_raw(
                            topic=event.topic,
                            key=event.key,
                            value=event.payload,
                        )
                        await repo.mark_published(event)
                        published += 1
                    except Exception as exc:
                        logger.error(
                            "outbox_publish_failed",
                            event_id=str(event.id),
                            error=str(exc),
                        )
                        await repo.mark_failed(event)

        if published:
            logger.info("outbox_batch_published", count=published)
        return published

    async def health_check(self) -> str:
        if await is_producer_ready():
            return "ok"
        return "not_ready"
