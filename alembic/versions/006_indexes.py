"""Add performance indexes for common query patterns.

Revision ID: 006
Revises: 005
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Entity queries by type (commonly filtered in API/cleanup)
    op.create_index("ix_entities_type", "entities", ["entity_type_id"])

    # Entity queries by created_at (time-range queries)
    op.create_index("ix_entities_created_at", "entities", ["created_at"])

    # Entity queries by confidence (cleanup jobs filter low-confidence)
    op.create_index("ix_entities_confidence", "entities", ["confidence"])

    # Content queries by created_at (time-range queries)
    op.create_index("ix_content_created_at", "content", ["created_at"])

    # EntityRelationship source+target composite (path queries)
    op.create_index(
        "ix_entity_relationships_source_target",
        "entity_relationships",
        ["source_entity_id", "target_entity_id"],
    )

    # OutboxEvent status+next_retry_at (outbox polling query)
    op.create_index(
        "ix_outbox_events_status_retry",
        "outbox_events",
        ["status", "next_retry_at"],
    )

    # PipelineJob status+created_at (job listing)
    op.create_index(
        "ix_pipeline_jobs_status_created",
        "pipeline_jobs",
        ["status", "created_at"],
    )

    # EntitySimilarity queries by score (similarity threshold filtering)
    op.create_index("ix_entity_similarity_score", "entity_similarity", ["similarity_score"])


def downgrade() -> None:
    op.drop_index("ix_entity_similarity_score", table_name="entity_similarity")
    op.drop_index("ix_pipeline_jobs_status_created", table_name="pipeline_jobs")
    op.drop_index("ix_outbox_events_status_retry", table_name="outbox_events")
    op.drop_index("ix_entity_relationships_source_target", table_name="entity_relationships")
    op.drop_index("ix_content_created_at", table_name="content")
    op.drop_index("ix_entities_confidence", table_name="entities")
    op.drop_index("ix_entities_created_at", table_name="entities")
    op.drop_index("ix_entities_type", table_name="entities")
