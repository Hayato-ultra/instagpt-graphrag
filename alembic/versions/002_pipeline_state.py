"""pipeline_jobs + pipeline_steps tables

Revision ID: 002
Revises: 001
Create Date: 2025-08-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pipeline_jobs table
    op.create_table(
        "pipeline_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed", "dead_letter",
                name="jobstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("current_step", sa.String(50), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result_metadata", JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pipeline_jobs_content_hash", "pipeline_jobs", ["content_hash"], unique=True)
    op.create_index("ix_pipeline_jobs_status", "pipeline_jobs", ["status"])
    op.create_index("ix_pipeline_jobs_priority", "pipeline_jobs", ["priority"])
    op.create_index("ix_pipeline_jobs_heartbeat", "pipeline_jobs", ["heartbeat_at"])

    # Create pipeline_steps table
    op.create_table(
        "pipeline_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("pipeline_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String(50), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "completed", "failed", "skipped",
                name="stepstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("checkpoint_data", JSONB(), server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pipeline_steps_job_id", "pipeline_steps", ["job_id"])
    op.create_index(
        "ix_pipeline_steps_job_status",
        "pipeline_steps",
        ["job_id", "status"],
    )
    op.create_unique_constraint(
        "uq_pipeline_step_job_name",
        "pipeline_steps",
        ["job_id", "step_name"],
    )

    # Add DEAD_LETTER to the existing jobstatus enum (safe to alter enum in PG)
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'dead_letter'")


def downgrade() -> None:
    op.drop_table("pipeline_steps")
    op.drop_table("pipeline_jobs")
    # Note: cannot remove enum value in PG; leaving dead_letter in jobstatus
