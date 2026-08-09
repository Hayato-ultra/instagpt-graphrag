"""initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Entity Type Table (create first, no dependencies) ---
    op.create_table(
        'entity_types',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
    )

    # --- Content Table ---
    op.create_table(
        'content',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('title', sa.Text, server_default=''),
        sa.Column('raw_text', sa.Text, server_default=''),
        sa.Column('markdown', sa.Text, server_default=''),
        sa.Column('summary', sa.Text, server_default=''),
        sa.Column('content_length', sa.Integer, server_default='0'),
        sa.Column('word_count', sa.Integer, server_default='0'),
        sa.Column('content_type', sa.String(50), server_default='unknown'),
        sa.Column('extraction_strategy', sa.String(100), server_default='webfetch'),
        sa.Column('metadata_', JSONB, server_default='{}'),
        sa.Column('entities_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_content_url', 'content', ['url'], unique=True)

    # --- Content Chunks Table ---
    op.create_table(
        'content_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('content_id', sa.String(36), sa.ForeignKey('content.id', ondelete='CASCADE'), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('token_count', sa.Integer, server_default='0'),
        sa.Column('header_path', sa.Text, server_default=''),
        sa.Column('header_level', sa.Integer, server_default='0'),
        sa.Column('metadata_', JSONB, server_default='{}'),
        sa.Column('embedding_id', sa.String(100)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_chunks_content_id', 'content_chunks', ['content_id'])

    # --- Topics Table ---
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('parent_id', sa.Integer, sa.ForeignKey('topics.id', ondelete='SET NULL')),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # --- SubTopics Table ---
    op.create_table(
        'subtopics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('topic_id', sa.Integer, sa.ForeignKey('topics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('topic_id', 'name', name='uq_subtopic_topic_name'),
    )

    # --- Entities Table ---
    op.create_table(
        'entities',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('entity_type_id', sa.Integer, sa.ForeignKey('entity_types.id'), nullable=False),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('summary', sa.Text, server_default=''),
        sa.Column('key_points', ARRAY(sa.Text), server_default='{}'),
        sa.Column('confidence', sa.Float, server_default='0.0'),
        sa.Column('qdrant_id', sa.String(100)),
        sa.Column('neo4j_id', sa.String(100)),
        sa.Column('source_text', sa.Text, server_default=''),
        sa.Column('metadata_', JSONB, server_default='{}'),
        sa.Column('version', sa.Integer, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_entity_name', 'entities', ['name'])
    op.create_index('ix_entity_type', 'entities', ['entity_type_id'])

    # --- Content-Entity Links ---
    op.create_table(
        'content_entities',
        sa.Column('content_id', sa.String(36), sa.ForeignKey('content.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('relevance', sa.Float, server_default='1.0'),
        sa.Column('chunk_id', sa.String(36)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # --- Content-Topic Links ---
    op.create_table(
        'content_topics',
        sa.Column('content_id', sa.String(36), sa.ForeignKey('content.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('topic_id', sa.Integer, sa.ForeignKey('topics.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('subtopic_id', sa.Integer, sa.ForeignKey('subtopics.id', ondelete='SET NULL')),
        sa.Column('content_type', sa.String(50), server_default='unknown'),
        sa.Column('topic_confidence', sa.Float, server_default='0.0'),
        sa.Column('type_confidence', sa.Float, server_default='0.0'),
        sa.Column('tags', ARRAY(sa.Text), server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # --- Entity Relationships ---
    op.create_table(
        'entity_relationships',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('source_entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('confidence', sa.Float, server_default='0.0'),
        sa.Column('source_content_id', sa.String(36), sa.ForeignKey('content.id', ondelete='SET NULL')),
        sa.Column('metadata_', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_rel_source', 'entity_relationships', ['source_entity_id'])
    op.create_index('ix_rel_target', 'entity_relationships', ['target_entity_id'])
    op.create_index('ix_rel_type', 'entity_relationships', ['relationship_type'])

    # --- Entity Similarity ---
    op.create_table(
        'entity_similarity',
        sa.Column('entity_a_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('entity_b_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('similarity_score', sa.Float, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # --- Analysis Jobs ---
    op.create_table(
        'analysis_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('content_id', sa.String(36), sa.ForeignKey('content.id', ondelete='SET NULL')),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('stage', sa.String(50)),
        sa.Column('error', sa.Text),
        sa.Column('result_metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime),
    )

    # --- Episodic Memories ---
    op.create_table(
        'episodic_memories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text, server_default=''),
        sa.Column('source_url', sa.Text, server_default=''),
        sa.Column('content_type', sa.String(50), server_default=''),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # --- Web References ---
    op.create_table(
        'web_references',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.Text, server_default=''),
        sa.Column('url', sa.Text, server_default=''),
        sa.Column('snippet', sa.Text, server_default=''),
        sa.Column('source', sa.String(100), server_default=''),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # --- Similar Tools ---
    op.create_table(
        'similar_tools',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('entity_id', sa.String(36), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('url', sa.Text, server_default=''),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # --- Output Files ---
    op.create_table(
        'output_files',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('content_id', sa.String(36), sa.ForeignKey('content.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.Text, nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('output_files')
    op.drop_table('similar_tools')
    op.drop_table('web_references')
    op.drop_table('episodic_memories')
    op.drop_table('analysis_jobs')
    op.drop_table('entity_similarity')
    op.drop_table('entity_relationships')
    op.drop_table('content_topics')
    op.drop_table('content_entities')
    op.drop_table('entities')
    op.drop_table('subtopics')
    op.drop_table('topics')
    op.drop_table('content_chunks')
    op.drop_table('content')
    op.drop_table('entity_types')
