import json
from datetime import (
    datetime,
    timezone,
)
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings
from app.core.logging import get_logger
from app.models.document import Document

logger = get_logger(__name__)


def _json_default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


class KafkaProducer:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=_json_default).encode("utf-8"),
            compression_type="gzip",
            acks="all",
            enable_idempotence=True,
            max_batch_size=32768,
            linger_ms=10,
        )
        await self._producer.start()
        logger.info("kafka_producer_started")

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("kafka_producer_stopped")

    @property
    def is_ready(self) -> bool:
        return self._producer is not None

    async def publish_raw(self, topic: str, key: str, value: dict[str, Any]) -> None:
        if not self._producer:
            raise RuntimeError("Producer not started")
        try:
            await self._producer.send_and_wait(
                topic,
                value=value,
                key=key.encode("utf-8"),
            )
        except KafkaConnectionError as exc:
            logger.error("kafka_publish_failed", topic=topic, key=key, error=str(exc))
            raise

    async def publish_decision(self, document: Document) -> None:
        message: dict[str, Any] = {
            "document_id": str(document.id),
            "external_id": document.external_id,
            "status": document.status,
            "decision_at": document.decision_at,
            "assigned_to_id": str(document.assigned_to_id) if document.assigned_to_id else None,
            "rejection_reason": document.rejection_reason,
            "payload": document.payload,
        }
        await self.publish_raw(
            topic=settings.KAFKA_OUTPUT_TOPIC,
            key=str(document.id),
            value=message,
        )
        logger.info(
            "document_published",
            document_id=str(document.id),
            status=document.status,
        )


_producer_instance: KafkaProducer | None = None


async def get_kafka_producer() -> KafkaProducer:
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = KafkaProducer()
        await _producer_instance.start()
    return _producer_instance


async def stop_kafka_producer() -> None:
    global _producer_instance
    if _producer_instance:
        await _producer_instance.stop()
        _producer_instance = None


async def is_producer_ready() -> bool:
    global _producer_instance
    return _producer_instance is not None and _producer_instance.is_ready
