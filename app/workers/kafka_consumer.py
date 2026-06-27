import asyncio
import json
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionFactory
from app.models.document import DocumentStatusEnum
from app.repositories.document_repository import DocumentRepository

logger = get_logger(__name__)


class DocumentConsumer:
    """Reads input topic messages and persists documents to PostgreSQL."""

    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_INPUT_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
            enable_auto_commit=False,
            max_poll_records=settings.KAFKA_MAX_POLL_RECORDS,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            "kafka_consumer_started",
            topic=settings.KAFKA_INPUT_TOPIC,
            group=settings.KAFKA_CONSUMER_GROUP,
        )

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("kafka_consumer_stopped")

    async def run(self) -> None:
        if not self._consumer:
            raise RuntimeError("Consumer not started")

        while self._running:
            try:
                batch = await self._consumer.getmany(timeout_ms=500, max_records=100)
                if not batch:
                    continue

                records: list[dict[str, Any]] = []
                for tp, messages in batch.items():
                    for msg in messages:
                        payload: dict[str, Any] = msg.value
                        records.append(
                            {
                                "external_id": str(payload.get("id", msg.offset)),
                                "source_topic": msg.topic,
                                "payload": payload,
                                "status": DocumentStatusEnum.PENDING,
                            }
                        )

                await self._persist_batch(records)
                await self._consumer.commit()
                logger.info("kafka_batch_processed", count=len(records))

            except KafkaConnectionError as exc:
                logger.error("kafka_connection_error", error=str(exc))
                await asyncio.sleep(5)
            except Exception as exc:
                logger.exception("kafka_consumer_error", error=str(exc))
                await asyncio.sleep(1)

    async def _persist_batch(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        async with AsyncSessionFactory() as session:
            async with session.begin():
                await DocumentRepository(session).bulk_insert_pending(records)


_consumer_instance: DocumentConsumer | None = None


async def run_consumer() -> None:
    global _consumer_instance
    retry_delay = 5
    max_retries = 10

    for attempt in range(max_retries):
        try:
            _consumer_instance = DocumentConsumer()
            await _consumer_instance.start()
            await _consumer_instance.run()
            break
        except KafkaConnectionError as exc:
            logger.warning(
                "kafka_startup_retry",
                attempt=attempt,
                error=str(exc),
                retry_in=retry_delay,
            )
            await asyncio.sleep(retry_delay)
    else:
        logger.error("kafka_consumer_failed_to_start")


async def stop_consumer() -> None:
    global _consumer_instance
    if _consumer_instance:
        await _consumer_instance.stop()
