"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    role_enum = postgresql.ENUM(
        "operator", "supervisor", "admin", name="role_enum", create_type=True
    )
    role_enum.create(op.get_bind(), checkfirst=True)

    doc_status_enum = postgresql.ENUM(
        "pending", "in_progress", "accepted", "rejected",
        name="document_status_enum", create_type=True
    )
    doc_status_enum.create(op.get_bind(), checkfirst=True)

    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("full_name", sa.String(256), nullable=True),
        sa.Column("role", postgresql.ENUM("operator", "supervisor", "admin", name="role_enum", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_id", "users", ["id"])

    # Documents table
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("source_topic", sa.String(256), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "in_progress", "accepted", "rejected", name="document_status_enum", create_type=False), nullable=False),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("external_id", "source_topic", name="uq_document_external"),
    )
    op.create_index("ix_documents_id", "documents", ["id"])
    op.create_index("ix_documents_external_id", "documents", ["external_id"])
    op.create_index("ix_documents_assigned_to_id", "documents", ["assigned_to_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # Partial index for fast PENDING queue lookups
    op.create_index(
        "ix_documents_pending_created",
        "documents",
        ["status", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS document_status_enum")
    op.execute("DROP TYPE IF EXISTS role_enum")
