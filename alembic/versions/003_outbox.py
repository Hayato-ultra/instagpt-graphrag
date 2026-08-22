"""outbox_events table

Revision ID: 003
Revises: 002
Create Date: 2025-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("aggregate_type", sa.String(50), nullable=False, server_default="entity"),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("payload", JSONB(), server_default="{}"),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed",
                name="outboxeventstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_outbox_events_status_created", "outbox_events", ["status", "created_at"])
    op.create_index(
        "ix_outbox_events_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    # Note: cannot remove enum value in PG; leaving outboxeventstatus types