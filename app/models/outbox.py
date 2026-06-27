import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    String,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.db.types import pg_str_enum


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class OutboxEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Transactional outbox — Kafka messages are written here in the same
    DB transaction as the business state change, then relayed asynchronously.
    """

    __tablename__ = "outbox_events"

    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(256), nullable=False)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        pg_str_enum(OutboxStatus, "outbox_status_enum"),
        nullable=False,
        default=OutboxStatus.PENDING,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
