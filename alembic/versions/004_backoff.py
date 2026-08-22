"""Add next_retry_at for exponential backoff on outbox retries.

Revision ID: 004
Revises: 003
Create Date: 2025-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_next_retry_at",
        "outbox_events",
        ["next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_next_retry_at", table_name="outbox_events")
    op.drop_column("outbox_events", "next_retry_at")
