"""Add provenance columns and RELATED entity type.

Revision ID: 005
Revises: 004
Create Date: 2025-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column("extraction_timestamp", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "entities",
        sa.Column("pipeline_version", sa.String(50), nullable=True),
    )
    op.add_column(
        "entities",
        sa.Column("model_version", sa.String(100), nullable=True),
    )
    op.add_column(
        "entities",
        sa.Column("embedding_version", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_entities_pipeline_version",
        "entities",
        ["pipeline_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_entities_pipeline_version", table_name="entities")
    op.drop_column("entities", "embedding_version")
    op.drop_column("entities", "model_version")
    op.drop_column("entities", "pipeline_version")
    op.drop_column("entities", "extraction_timestamp")
