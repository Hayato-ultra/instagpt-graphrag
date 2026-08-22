"""SQLAlchemy models for the knowledge graph database.

Maps all existing data structures to normalized PostgreSQL tables.
Every field from the original models has a destination:
  1. Direct relational column
  2. Related table (junction/foreign key)
  3. JSONB metadata column
  4. JSONB array for dynamic/unpredictable data
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.database.base import Base

# ─── Enums ────────────────────────────────────────────────────────────────────

class ContentType(str, enum.Enum):
    """Content classification types."""
    TUTORIAL = "tutorial"
    BEST_PRACTICE = "best_practice"
    BUG_FIX = "bug_fix"
    TIP = "tip"
    COMPARISON = "comparison"
    ARCHITECTURE_DECISION = "architecture_decision"
    TOOL_REVIEW = "tool_review"
    MIGRATION_GUIDE = "migration_guide"
    DOCUMENTATION = "documentation"
    BLOG_POST = "blog_post"
    UNKNOWN = "unknown"


class EntityType(str, enum.Enum):
    """Entity classification types."""
    WEB_APP = "web_app"
    MOBILE_APP = "mobile_app"
    TOOL = "tool"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    PLATFORM = "platform"
    SERVICE = "service"
    API = "api"
    DATABASE = "database"
    LANGUAGE = "language"
    CREATIVE_SOFTWARE = "creative_software"
    CONCEPT = "concept"
    PATTERN = "pattern"
    TECHNIQUE = "technique"
    RELATED = "related"
    UNKNOWN = "unknown"


class TopicCategory(str, enum.Enum):
    """Topic taxonomy categories."""
    FRONTEND = "frontend"
    BACKEND = "backend"
    DEVOPS = "devops"
    AI_ML = "ai_ml"
    DATABASE = "database"
    SECURITY = "security"
    TESTING = "testing"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    MOBILE = "mobile"
    CLOUD = "cloud"
    OTHER = "other"


class JobStatus(str, enum.Enum):
    """Analysis job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class StepStatus(str, enum.Enum):
    """Pipeline step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobPriority(int, enum.Enum):
    """Pipeline job priority. Lower = higher priority."""
    URGENT = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class OutboxEventStatus(str, enum.Enum):
    """Status of a transactional outbox event."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OutboxEventType(str, enum.Enum):
    """Event types emitted by the outbox.

    PostgreSQL is the source of truth; each event carries the full payload
    needed to rebuild the projection (Neo4j node or Qdrant point) idempotently.
    """
    ENTITY_UPSERT = "entity.upsert"
    ENTITY_DELETE = "entity.delete"
    RELATIONSHIP_UPSERT = "relationship.upsert"
    CONTENT_CHUNKS_UPSERT = "content.chunks.upsert"
    CONTENT_DELETE = "content.delete"


class RelationshipType(str, enum.Enum):
    """Entity-to-entity relationship types."""
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    IMPLEMENTS = "IMPLEMENTS"
    REPLACES = "REPLACES"
    INTEGRATES_WITH = "INTEGRATES_WITH"
    PART_OF = "PART_OF"
    ALTERNATIVE_TO = "ALTERNATIVE_TO"
    ENABLES = "ENABLES"
    EVOLVED_FROM = "EVOLVED_FROM"
    COMPLEMENTS = "COMPLEMENTS"
    SIMILAR_TO = "SIMILAR_TO"
    CO_OCCURS_WITH = "CO_OCCURS_WITH"
    BELONGS_TO = "BELONGS_TO"
    RELATED_TO = "RELATED_TO"
    UPDATES = "UPDATES"


# ─── Helper ───────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())


# ─── Content (URLs / Videos / Posts) ──────────────────────────────────────────

class Content(Base):
    """Source content (URL, video, post) that was processed.

    OLD: videos dict in src/api/__init__.py
    OLD: ExtractedContent in pipeline
    OLD: source_url on entities
    """
    __tablename__ = "content"

    id = Column(String(36), primary_key=True, default=_uuid)
    url = Column(Text, nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False, default="")
    raw_text = Column(Text, nullable=False, default="")
    markdown = Column(Text, nullable=False, default="")
    content_length = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    extraction_strategy = Column(String(50), default="webfetch")
    summary = Column(Text, default="")
    entities_count = Column(Integer, default=0)
    transcript = Column(Text, default="")
    thumbnail = Column(Text, default="")
    channel = Column(String(255), default="")
    duration = Column(Float, default=0.0)
    # Preserve any extra metadata from extraction
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=datetime.utcnow)

    # Relationships
    chunks = relationship("ContentChunk", back_populates="content", cascade="all, delete-orphan")
    content_entities = relationship("ContentEntity", back_populates="content", cascade="all, delete-orphan")
    content_topics = relationship("ContentTopic", back_populates="content", cascade="all, delete-orphan")
    analysis_jobs = relationship("AnalysisJob", back_populates="content")
    outputs = relationship("OutputFile", back_populates="content")


class ContentChunk(Base):
    """Semantic text chunks from content for embedding.

    OLD: DocumentChunk in pipeline
    """
    __tablename__ = "content_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    content_id = Column(String(36), ForeignKey("content.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    header_path = Column(Text, default="")
    header_level = Column(Integer, default=0)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    content = relationship("Content", back_populates="chunks")


# ─── Entity Types ─────────────────────────────────────────────────────────────

class EntityTypeRow(Base):
    """Lookup table for entity types.

    OLD: EntityType enum in config/models.py
    """
    __tablename__ = "entity_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(Text, default="")

    # Relationships
    entities = relationship("Entity", back_populates="entity_type")


# ─── Entities ─────────────────────────────────────────────────────────────────

class Entity(Base):
    """Detected entity (tool, framework, concept, etc.)

    OLD: EnrichedEntity in enrichment
    OLD: Entity node in Neo4j
    """
    __tablename__ = "entities"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False, index=True)
    entity_type_id = Column(Integer, ForeignKey("entity_types.id"), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    summary = Column(Text, default="")
    key_points = Column(JSONB, default=list)  # List[str]
    confidence = Column(Float, default=0.0)
    version = Column(Integer, default=1)
    # Qdrant vector ID for linking to vector store
    qdrant_id = Column(String(36), nullable=True, unique=True)
    # Neo4j node ID for linking to graph store
    neo4j_id = Column(String(255), nullable=True, unique=True)
    source_text = Column(Text, default="")  # Full source transcript for LLM context
    # Provenance — tracks exactly how this entity was created
    extraction_timestamp = Column(DateTime, nullable=True)
    pipeline_version = Column(String(50), nullable=True)
    model_version = Column(String(100), nullable=True)
    embedding_version = Column(String(100), nullable=True)
    # Temporal knowledge (TODO #57)
    valid_from = Column(DateTime, nullable=True)  # When this entity became valid
    valid_until = Column(DateTime, nullable=True)  # When this entity expires (null = permanent)
    # Preserve raw enrichment data
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=datetime.utcnow)

    # Relationships
    entity_type = relationship("EntityTypeRow", back_populates="entities")
    content_entities = relationship("ContentEntity", back_populates="entity", cascade="all, delete-orphan")
    content_topics = relationship("ContentTopic", back_populates="entity")
    source_relationships = relationship(
        "EntityRelationship",
        foreign_keys="EntityRelationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    target_relationships = relationship(
        "EntityRelationship",
        foreign_keys="EntityRelationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )
    similar_from = relationship(
        "EntitySimilarity",
        foreign_keys="EntitySimilarity.entity_a_id",
        back_populates="entity_a",
        cascade="all, delete-orphan",
    )
    similar_to = relationship(
        "EntitySimilarity",
        foreign_keys="EntitySimilarity.entity_b_id",
        back_populates="entity_b",
        cascade="all, delete-orphan",
    )
    episodic_memories = relationship("EpisodicMemory", back_populates="entity", cascade="all, delete-orphan")
    web_references = relationship("WebReference", back_populates="entity", cascade="all, delete-orphan")
    similar_tools = relationship("SimilarTool", back_populates="entity", cascade="all, delete-orphan")
    primary_topics = relationship("ContentTopic", back_populates="entity", overlaps="content_topics")

    __table_args__ = (
        Index("ix_entities_name_lower", "name"),
        UniqueConstraint("name", "entity_type_id", name="uq_entity_name_type"),
    )


# ─── Topics ───────────────────────────────────────────────────────────────────

class Topic(Base):
    """Topic category.

    OLD: TopicCategory enum
    OLD: Topic node in Neo4j
    """
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    subtopics = relationship("SubTopic", back_populates="topic", cascade="all, delete-orphan")
    content_topics = relationship("ContentTopic", back_populates="topic")


class SubTopic(Base):
    """Subtopic within a topic category.

    OLD: sub_topics list on CategorizedItem
    OLD: SubTopic node in Neo4j
    """
    __tablename__ = "subtopics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    topic = relationship("Topic", back_populates="subtopics")
    content_topics = relationship("ContentTopic", back_populates="subtopic")

    __table_args__ = (
        UniqueConstraint("topic_id", "name", name="uq_subtopic_topic_name"),
    )


# ─── Junction Tables ──────────────────────────────────────────────────────────

class ContentEntity(Base):
    """Links content to detected entities.

    OLD: entity.source_chunk_id → content relationship
    OLD: content_entities in pipeline output
    """
    __tablename__ = "content_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(String(36), ForeignKey("content.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance = Column(Float, default=1.0)  # How relevant this entity is to this content
    chunk_id = Column(String(36), ForeignKey("content_chunks.id", ondelete="SET NULL"), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    content = relationship("Content", back_populates="content_entities")
    entity = relationship("Entity", back_populates="content_entities")
    chunk = relationship("ContentChunk")

    __table_args__ = (
        UniqueConstraint("content_id", "entity_id", name="uq_content_entity"),
        Index("ix_content_entities_entity_id", "entity_id"),
    )


class ContentTopic(Base):
    """Links content/entities to topics.

    OLD: CategorizedItem.primary_topic
    OLD: CategorizedItem.sub_topics
    OLD: BELONGS_TO edges in Neo4j
    """
    __tablename__ = "content_topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(String(36), ForeignKey("content.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id", ondelete="SET NULL"), nullable=True)
    content_type = Column(SAEnum(ContentType), default=ContentType.UNKNOWN)
    topic_confidence = Column(Float, default=0.0)
    type_confidence = Column(Float, default=0.0)
    tags = Column(JSONB, default=list)  # List[str]
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    content = relationship("Content", back_populates="content_topics")
    entity = relationship("Entity", back_populates="primary_topics")
    topic = relationship("Topic", back_populates="content_topics")
    subtopic = relationship("SubTopic", back_populates="content_topics")

    __table_args__ = (
        Index("ix_content_topics_topic_id", "topic_id"),
    )


# ─── Entity Relationships ─────────────────────────────────────────────────────

class EntityRelationship(Base):
    """Explicit relationships between entities.

    OLD: ExtractedRelationship in enrichment
    OLD: USES, DEPENDS_ON, etc. edges in Neo4j
    """
    __tablename__ = "entity_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(SAEnum(RelationshipType), nullable=False)
    description = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    source_content_id = Column(String(36), ForeignKey("content.id", ondelete="SET NULL"), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    source_entity = relationship("Entity", foreign_keys=[source_entity_id], back_populates="source_relationships")
    target_entity = relationship("Entity", foreign_keys=[target_entity_id], back_populates="target_relationships")
    source_content = relationship("Content")

    __table_args__ = (
        UniqueConstraint("source_entity_id", "target_entity_id", "relationship_type", name="uq_entity_relationship"),
        Index("ix_entity_relationships_type", "relationship_type"),
    )


class EntitySimilarity(Base):
    """Embedding-based similarity between entities.

    OLD: SIMILAR_TO edges in Neo4j
    OLD: Similarity thresholds in graph_store
    """
    __tablename__ = "entity_similarity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_a_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_b_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    entity_a = relationship("Entity", foreign_keys=[entity_a_id], back_populates="similar_from")
    entity_b = relationship("Entity", foreign_keys=[entity_b_id], back_populates="similar_to")

    __table_args__ = (
        UniqueConstraint("entity_a_id", "entity_b_id", name="uq_entity_similarity"),
    )


# ─── Analysis Jobs ────────────────────────────────────────────────────────────

class AnalysisJob(Base):
    """Tracks URL analysis jobs.

    OLD: analyses dict in src/api/__init__.py
    OLD: jobs dict in src/output/frontend.py
    """
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    content_id = Column(String(36), ForeignKey("content.id", ondelete="SET NULL"), nullable=True, index=True)
    url = Column(Text, nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    stage = Column(String(50), default="starting")
    error = Column(Text, nullable=True)
    # Preserve full processing result as JSONB
    result_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    content = relationship("Content", back_populates="analysis_jobs")

    __table_args__ = (
        Index("ix_analysis_jobs_status", "status"),
        Index("ix_analysis_jobs_created_at", "created_at"),
    )


# ─── Pipeline Jobs ───────────────────────────────────────────────────────────

class PipelineJob(Base):
    """Resumable pipeline job with content-hash idempotency.

    Replaces AnalysisJob for pipeline work. Each job runs through ordered
    stages (extract→chunk→embed→enrich→categorize→format→graph_update).
    Completed stages are never re-run; crash-recovery resets RUNNING→PENDING.
    """
    __tablename__ = "pipeline_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    url = Column(Text, nullable=False)
    status = Column(
        SAEnum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    current_step = Column(String(50), nullable=True)
    priority = Column(Integer, default=JobPriority.NORMAL, nullable=False)
    attempt = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    error = Column(Text, nullable=True)
    result_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)

    # Relationships
    steps = relationship(
        "PipelineStep",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="PipelineStep.step_order",
    )


class PipelineStep(Base):
    """Checkpoint record for a single pipeline stage.

    Once status=COMPLETED the stage is never re-run for this job.
    On crash recovery any RUNNING steps are reset to PENDING.
    """
    __tablename__ = "pipeline_steps"

    id = Column(String(36), primary_key=True, default=_uuid)
    job_id = Column(
        String(36),
        ForeignKey("pipeline_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_name = Column(String(50), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(
        SAEnum(StepStatus),
        default=StepStatus.PENDING,
        nullable=False,
    )
    # Opaque checkpoint data for resume (e.g. extracted content hash, chunk count)
    checkpoint_data = Column(JSONB, default=dict)
    error = Column(Text, nullable=True)
    attempt = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    job = relationship("PipelineJob", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("job_id", "step_name", name="uq_pipeline_step_job_name"),
    )  # ix_pipeline_steps_job_status created by migration 002


# ─── Outbox ───────────────────────────────────────────────────────────────────

class OutboxEvent(Base):
    """Transactional outbox event for projecting PG state to Neo4j/Qdrant.

    PostgreSQL is the canonical source of truth. When an entity/relationship/
    content is written, an outbox event is inserted in the same transaction.
    A worker later consumes the event and applies the projection to Neo4j and
    Qdrant idempotently (deterministic IDs, MERGE-based writes).
    """
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(SAEnum(OutboxEventType), nullable=False, index=True)
    # Aggregate the event refers to (entity id, content id, etc.)
    aggregate_type = Column(String(50), nullable=False, default="entity")
    aggregate_id = Column(String(255), nullable=False, index=True)
    # Serialized payload needed to rebuild the projection idempotently
    payload = Column(JSONB, default=dict)
    status = Column(
        SAEnum(OutboxEventStatus),
        default=OutboxEventStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    processed_at = Column(DateTime, nullable=True)


# ─── Episodic Memory ─────────────────────────────────────────────────────────

class EpisodicMemory(Base):
    """Version history of entity updates.

    OLD: EpisodicMemory node in Neo4j
    OLD: version field on entities
    """
    __tablename__ = "episodic_memories"

    id = Column(String(36), primary_key=True, default=_uuid)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, default="")
    source_url = Column(Text, default="")
    content_type = Column(String(50), default="")
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)

    # Relationships
    entity = relationship("Entity", back_populates="episodic_memories")


# ─── Web References & Similar Tools (JSONB arrays on Entity) ──────────────────

class WebReference(Base):
    """Web search results associated with an entity.

    OLD: entity.web_info list of {title, url, snippet, source}
    """
    __tablename__ = "web_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(Text, default="")
    url = Column(Text, nullable=False)
    snippet = Column(Text, default="")
    source = Column(String(50), default="")
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    entity = relationship("Entity", back_populates="web_references")

    __table_args__ = (
        Index("ix_web_references_entity_id", "entity_id"),
    )


class SimilarTool(Base):
    """Similar/alternative tools for an entity.

    OLD: entity.similar_tools list of {name, description, url}
    """
    __tablename__ = "similar_tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    url = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    entity = relationship("Entity", back_populates="similar_tools")

    __table_args__ = (
        Index("ix_similar_tools_entity_id", "entity_id"),
    )


# ─── Output Files ─────────────────────────────────────────────────────────────

class OutputFile(Base):
    """Generated output files (Markdown, JSON).

    OLD: markdown_path, json_path in PipelineResult
    OLD: output files in ./outputs/
    """
    __tablename__ = "output_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(String(36), ForeignKey("content.id", ondelete="SET NULL"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(20), nullable=False)  # "markdown", "json"
    file_size = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    content = relationship("Content", back_populates="outputs")
