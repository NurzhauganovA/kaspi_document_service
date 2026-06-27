import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.db.types import pg_str_enum


class RoleEnum(StrEnum):
    OPERATOR = "operator"       # can claim & decide on documents
    SUPERVISOR = "supervisor"   # operator + statistics
    ADMIN = "admin"             # full access


class DocumentStatusEnum(StrEnum):
    PENDING = "pending"         # in queue, not yet claimed
    IN_PROGRESS = "in_progress" # claimed by operator, awaiting decision
    ACCEPTED = "accepted"       # operator accepted
    REJECTED = "rejected"       # operator rejected


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(256))
    role: Mapped[RoleEnum] = mapped_column(
        pg_str_enum(RoleEnum, "role_enum"),
        nullable=False,
        default=RoleEnum.OPERATOR,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Back-references
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="assigned_to", lazy="select"
    )

    def has_role(self, *roles: RoleEnum) -> bool:
        return self.role in roles


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    # Source data from Kafka
    external_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    source_topic: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Queue state
    status: Mapped[DocumentStatusEnum] = mapped_column(
        pg_str_enum(DocumentStatusEnum, "document_status_enum"),
        nullable=False,
        default=DocumentStatusEnum.PENDING,
        index=True,
    )

    # Assignment
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Decision
    decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Output queue
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    assigned_to: Mapped[User | None] = relationship("User", back_populates="documents")

    __table_args__ = (
        # Partial index: fast retrieval of next PENDING document
        Index(
            "ix_documents_pending_created",
            "status",
            "created_at",
            postgresql_where="status = 'pending'",
        ),
        UniqueConstraint("external_id", "source_topic", name="uq_document_external"),
    )
