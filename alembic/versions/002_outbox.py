"""Add transactional outbox table

Revision ID: 002_outbox
Revises: 001_initial
Create Date: 2026-06-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_outbox"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    outbox_status_enum = postgresql.ENUM(
        "pending", "published", "failed", name="outbox_status_enum", create_type=True
    )
    outbox_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(256), nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "published", "failed", name="outbox_status_enum", create_type=False
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_id", "outbox_events", ["id"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.execute("DROP TYPE IF EXISTS outbox_status_enum")
