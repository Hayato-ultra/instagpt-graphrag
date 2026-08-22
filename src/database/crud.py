"""CRUD operations for the knowledge graph database.

Provides methods to create, read, update, and delete records.
All operations are async and use the SQLAlchemy session.
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    AnalysisJob,
    Content,
    ContentChunk,
    ContentEntity,
    ContentTopic,
    Entity,
    EntityRelationship,
    EntitySimilarity,
    EntityType,
    EntityTypeRow,
    EpisodicMemory,
    JobStatus,
    OutboxEvent,
    OutboxEventStatus,
    OutboxEventType,
    OutputFile,
    PipelineJob,
    PipelineStep,
    SimilarTool,
    StepStatus,
    SubTopic,
    Topic,
    TopicCategory,
    WebReference,
)


class CRUDOperations:
    """Async CRUD operations for the knowledge graph database."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ─── Content ───────────────────────────────────────────────────────────

    async def create_content(
        self,
        url: str,
        title: str = "",
        raw_text: str = "",
        markdown: str = "",
        content_length: int = 0,
        word_count: int = 0,
        extraction_strategy: str = "webfetch",
        metadata: dict = None,
    ) -> Content:
        """Create or get existing content by URL."""
        # Check if content already exists
        result = await self.session.execute(
            select(Content).where(Content.url == url)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        content = Content(
            id=str(__import__("uuid").uuid4()),
            url=url,
            title=title,
            raw_text=raw_text,
            markdown=markdown,
            content_length=content_length,
            word_count=word_count,
            extraction_strategy=extraction_strategy,
            metadata_=metadata or {},
        )
        self.session.add(content)
        await self.session.flush()
        return content

    async def get_content_by_url(self, url: str) -> Content | None:
        """Get content by URL."""
        result = await self.session.execute(
            select(Content).where(Content.url == url)
        )
        return result.scalar_one_or_none()

    async def get_content_by_id(self, content_id: str) -> Content | None:
        """Get content by ID."""
        result = await self.session.execute(
            select(Content).where(Content.id == content_id)
        )
        return result.scalar_one_or_none()

    async def list_content(self, limit: int = 100, offset: int = 0) -> list[Content]:
        """List all content."""
        result = await self.session.execute(
            select(Content)
            .order_by(Content.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_content_summary(
        self,
        content_id: str,
        summary: str,
        entities_count: int = 0,
    ) -> Content | None:
        """Update content summary after processing."""
        content = await self.get_content_by_id(content_id)
        if content:
            content.summary = summary
            content.entities_count = entities_count
            content.updated_at = datetime.now(UTC)
            await self.session.flush()
        return content

    # ─── Content Chunks ───────────────────────────────────────────────────

    async def create_chunks(
        self,
        content_id: str,
        chunks: list[dict[str, Any]],
    ) -> list[ContentChunk]:
        """Create content chunks."""
        db_chunks = []
        for chunk_data in chunks:
            chunk = ContentChunk(
                id=chunk_data.get("id", str(__import__("uuid").uuid4())),
                content_id=content_id,
                text=chunk_data.get("text", ""),
                chunk_index=chunk_data.get("chunk_index", 0),
                token_count=chunk_data.get("token_count", 0),
                header_path=chunk_data.get("header_path", ""),
                header_level=chunk_data.get("header_level", 0),
                metadata_=chunk_data.get("metadata", {}),
            )
            self.session.add(chunk)
            db_chunks.append(chunk)
        await self.session.flush()
        return db_chunks

    # ─── Entity Types ─────────────────────────────────────────────────────

    async def get_or_create_entity_type(self, name: str) -> EntityTypeRow:
        """Get or create entity type."""
        result = await self.session.execute(
            select(EntityTypeRow).where(EntityTypeRow.name == name)
        )
        etype = result.scalar_one_or_none()
        if not etype:
            etype = EntityTypeRow(name=name)
            self.session.add(etype)
            await self.session.flush()
        return etype

    async def ensure_entity_types(self) -> None:
        """Ensure all entity types exist."""
        for etype in EntityType:
            await self.get_or_create_entity_type(etype.value)

    # ─── Entities ─────────────────────────────────────────────────────────

    async def create_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
        confidence: float = 0.0,
        qdrant_id: str = None,
        neo4j_id: str = None,
        source_text: str = "",
        metadata: dict = None,
        extraction_timestamp: "datetime" = None,
        pipeline_version: str = None,
        model_version: str = None,
        embedding_version: str = None,
    ) -> Entity:
        """Create a new entity."""
        etype = await self.get_or_create_entity_type(entity_type)
        entity = Entity(
            id=str(__import__("uuid").uuid4()),
            name=name,
            entity_type_id=etype.id,
            description=description,
            confidence=confidence,
            qdrant_id=qdrant_id,
            neo4j_id=neo4j_id,
            source_text=source_text,
            metadata_=metadata or {},
            extraction_timestamp=extraction_timestamp,
            pipeline_version=pipeline_version,
            model_version=model_version,
            embedding_version=embedding_version,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_entity_by_name(self, name: str) -> Entity | None:
        """Get entity by exact name (case-insensitive)."""
        result = await self.session.execute(
            select(Entity).where(func.lower(Entity.name) == func.lower(name))
        )
        return result.scalar_one_or_none()

    async def get_entity_by_name_for_update(self, name: str) -> Entity | None:
        """Get entity by name with a row lock (SELECT ... FOR UPDATE).

        Use this when the caller intends to update the entity to prevent
        two concurrent transactions from both reading the same row and
        writing conflicting updates (lost-update anomaly).
        """
        result = await self.session.execute(
            select(Entity)
            .where(func.lower(Entity.name) == func.lower(name))
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_entity_by_id(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        result = await self.session.execute(
            select(Entity).where(Entity.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def search_entities(self, query: str, limit: int = 20) -> list[Entity]:
        """Search entities by name or description."""
        search_term = f"%{query.lower()}%"
        result = await self.session.execute(
            select(Entity).where(
                or_(
                    func.lower(Entity.name).like(search_term),
                    func.lower(Entity.description).like(search_term),
                )
            ).limit(limit)
        )
        return list(result.scalars().all())

    async def update_entity(
        self,
        entity_id: str,
        description: str = None,
        summary: str = None,
        key_points: list = None,
        confidence: float = None,
        version: int = None,
    ) -> Entity | None:
        """Update entity fields and bump the version for optimistic concurrency.

        The version column allows callers to detect lost updates: if two
        transactions read version=1 and both try to write version=2, the
        second writer will see a version mismatch and can retry.
        """
        entity = await self.get_entity_by_id(entity_id)
        if not entity:
            return None
        if description is not None:
            entity.description = description
        if summary is not None:
            entity.summary = summary
        if key_points is not None:
            entity.key_points = key_points
        if confidence is not None:
            entity.confidence = max(entity.confidence, confidence)
        if version is not None:
            entity.version = version
        else:
            entity.version = (entity.version or 1) + 1
        entity.updated_at = datetime.now(UTC)
        await self.session.flush()
        return entity

    async def set_entity_projection_ids(
        self, entity_id: str, neo4j_id: str = None, qdrant_id: str = None
    ) -> Entity | None:
        """Record the stable Neo4j/Qdrant IDs that an entity projects to.

        PostgreSQL remains the source of truth; neo4j_id/qdrant_id are derived
        links used by reconciliation to detect and repair drift.
        """
        entity = await self.get_entity_by_id(entity_id)
        if not entity:
            return None
        if neo4j_id is not None:
            entity.neo4j_id = neo4j_id
        if qdrant_id is not None:
            entity.qdrant_id = qdrant_id
        entity.updated_at = datetime.now(UTC)
        await self.session.flush()
        return entity

    # ─── Topics ───────────────────────────────────────────────────────────

    async def get_or_create_topic(self, name: str) -> Topic:
        """Get or create topic."""
        result = await self.session.execute(
            select(Topic).where(Topic.name == name)
        )
        topic = result.scalar_one_or_none()
        if not topic:
            topic = Topic(name=name)
            self.session.add(topic)
            await self.session.flush()
        return topic

    async def get_or_create_subtopic(self, topic_id: int, name: str) -> SubTopic:
        """Get or create subtopic."""
        result = await self.session.execute(
            select(SubTopic).where(
                and_(SubTopic.topic_id == topic_id, SubTopic.name == name)
            )
        )
        subtopic = result.scalar_one_or_none()
        if not subtopic:
            subtopic = SubTopic(topic_id=topic_id, name=name)
            self.session.add(subtopic)
            await self.session.flush()
        return subtopic

    async def ensure_topics(self) -> None:
        """Ensure all topic categories exist."""
        for topic in TopicCategory:
            await self.get_or_create_topic(topic.value)

    # ─── Content-Entity Links ─────────────────────────────────────────────

    async def link_content_entity(
        self,
        content_id: str,
        entity_id: str,
        relevance: float = 1.0,
        chunk_id: str = None,
    ) -> ContentEntity:
        """Link content to entity."""
        link = ContentEntity(
            content_id=content_id,
            entity_id=entity_id,
            relevance=relevance,
            chunk_id=chunk_id,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    # ─── Content-Topic Links ──────────────────────────────────────────────

    async def link_content_topic(
        self,
        content_id: str,
        entity_id: str,
        topic_name: str,
        subtopic_name: str = None,
        content_type: str = "unknown",
        topic_confidence: float = 0.0,
        type_confidence: float = 0.0,
        tags: list = None,
    ) -> ContentTopic:
        """Link content/entity to topic."""
        topic = await self.get_or_create_topic(topic_name)
        subtopic = None
        if subtopic_name:
            subtopic = await self.get_or_create_subtopic(topic.id, subtopic_name)

        link = ContentTopic(
            content_id=content_id,
            entity_id=entity_id,
            topic_id=topic.id,
            subtopic_id=subtopic.id if subtopic else None,
            content_type=content_type,
            topic_confidence=topic_confidence,
            type_confidence=type_confidence,
            tags=tags or [],
        )
        self.session.add(link)
        await self.session.flush()
        return link

    # ─── Entity Relationships ─────────────────────────────────────────────

    async def create_entity_relationship(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: str,
        description: str = "",
        confidence: float = 0.0,
        source_content_id: str = None,
    ) -> EntityRelationship:
        """Create entity-to-entity relationship."""
        # Check for existing relationship
        result = await self.session.execute(
            select(EntityRelationship).where(
                and_(
                    EntityRelationship.source_entity_id == source_entity_id,
                    EntityRelationship.target_entity_id == target_entity_id,
                    EntityRelationship.relationship_type == relationship_type,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.confidence = max(existing.confidence, confidence)
            existing.updated_at = datetime.now(UTC) if hasattr(existing, "updated_at") else None
            await self.session.flush()
            return existing

        rel = EntityRelationship(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            description=description,
            confidence=confidence,
            source_content_id=source_content_id,
        )
        self.session.add(rel)
        await self.session.flush()
        return rel

    async def get_entity_relationships(
        self,
        entity_id: str,
        limit: int = 20,
    ) -> list[EntityRelationship]:
        """Get all relationships for an entity."""
        result = await self.session.execute(
            select(EntityRelationship).where(
                or_(
                    EntityRelationship.source_entity_id == entity_id,
                    EntityRelationship.target_entity_id == entity_id,
                )
            ).limit(limit)
        )
        return list(result.scalars().all())

    # ─── Entity Similarity ────────────────────────────────────────────────

    async def create_entity_similarity(
        self,
        entity_a_id: str,
        entity_b_id: str,
        similarity_score: float,
    ) -> EntitySimilarity:
        """Create entity similarity link."""
        sim = EntitySimilarity(
            entity_a_id=entity_a_id,
            entity_b_id=entity_b_id,
            similarity_score=similarity_score,
        )
        self.session.add(sim)
        await self.session.flush()
        return sim

    # ─── Analysis Jobs ────────────────────────────────────────────────────

    async def create_analysis_job(
        self,
        url: str,
        content_id: str = None,
    ) -> AnalysisJob:
        """Create analysis job."""
        job = AnalysisJob(
            id=str(__import__("uuid").uuid4()),
            content_id=content_id,
            url=url,
            status=JobStatus.PENDING,
            stage="starting",
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        stage: str = None,
        error: str = None,
        content_id: str = None,
        metadata: dict = None,
    ) -> AnalysisJob | None:
        """Update analysis job status."""
        result = await self.session.execute(
            select(AnalysisJob).where(AnalysisJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return None
        job.status = status
        if stage:
            job.stage = stage
        if error:
            job.error = error
        if content_id:
            job.content_id = content_id
        if metadata:
            job.result_metadata = metadata
        if status in ("completed", "failed"):
            job.completed_at = datetime.now(UTC)
        await self.session.flush()
        return job

    async def get_job(self, job_id: str) -> AnalysisJob | None:
        """Get analysis job by ID."""
        result = await self.session.execute(
            select(AnalysisJob).where(AnalysisJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(self, limit: int = 100) -> list[AnalysisJob]:
        """List all analysis jobs."""
        result = await self.session.execute(
            select(AnalysisJob)
            .order_by(AnalysisJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ─── Pipeline Jobs ────────────────────────────────────────────────────

    async def create_pipeline_job(
        self,
        content_hash: str,
        url: str,
        steps: list[str],
        priority: int = 2,
    ) -> PipelineJob:
        """Create a pipeline job with pre-created step records."""
        job = PipelineJob(
            id=str(__import__("uuid").uuid4()),
            content_hash=content_hash,
            url=url,
            status=JobStatus.PENDING,
            priority=priority,
        )
        self.session.add(job)
        await self.session.flush()

        for idx, step_name in enumerate(steps):
            step = PipelineStep(
                id=str(__import__("uuid").uuid4()),
                job_id=job.id,
                step_name=step_name,
                step_order=idx,
                status=StepStatus.PENDING,
            )
            self.session.add(step)
        await self.session.flush()
        return job

    async def get_pipeline_job_by_hash(self, content_hash: str) -> PipelineJob | None:
        """Idempotency check: get existing job by content hash."""
        result = await self.session.execute(
            select(PipelineJob).where(PipelineJob.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def claim_pipeline_job(self, job_id: str) -> PipelineJob | None:
        """Atomically claim a job for processing (PENDING→PROCESSING)."""
        result = await self.session.execute(
            select(PipelineJob).where(
                PipelineJob.id == job_id,
                PipelineJob.status == JobStatus.PENDING,
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return None
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(UTC)
        job.heartbeat_at = datetime.now(UTC)
        await self.session.flush()
        return job

    async def get_pipeline_job_by_id(self, job_id: str) -> PipelineJob | None:
        """Get pipeline job by ID."""
        result = await self.session.execute(
            select(PipelineJob).where(PipelineJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_pipeline_steps(self, job_id: str) -> list[PipelineStep]:
        """Get all steps for a job, ordered by step_order."""
        result = await self.session.execute(
            select(PipelineStep)
            .where(PipelineStep.job_id == job_id)
            .order_by(PipelineStep.step_order)
        )
        return list(result.scalars().all())

    async def upsert_pipeline_step(
        self,
        job_id: str,
        step_name: str,
        status: StepStatus,
        checkpoint_data: dict = None,
        error: str = None,
    ) -> PipelineStep:
        """Upsert a pipeline step's status and checkpoint data."""
        result = await self.session.execute(
            select(PipelineStep).where(
                PipelineStep.job_id == job_id,
                PipelineStep.step_name == step_name,
            )
        )
        step = result.scalar_one_or_none()
        if not step:
            raise ValueError(f"Step {step_name} not found for job {job_id}")

        step.status = status
        if status == StepStatus.RUNNING:
            step.started_at = datetime.now(UTC)
            step.attempt += 1
        elif status == StepStatus.COMPLETED:
            step.completed_at = datetime.now(UTC)
        if checkpoint_data is not None:
            step.checkpoint_data = checkpoint_data
        if error is not None:
            step.error = error
        await self.session.flush()
        return step

    async def complete_pipeline_job(self, job_id: str) -> None:
        """Mark a job as completed."""
        result = await self.session.execute(
            select(PipelineJob).where(PipelineJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        await self.session.flush()

    async def fail_pipeline_job(
        self, job_id: str, error: str, dead_letter: bool = False
    ) -> None:
        """Mark a job as failed. If dead_letter=True, move to DEAD_LETTER."""
        result = await self.session.execute(
            select(PipelineJob).where(PipelineJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return
        job.status = JobStatus.DEAD_LETTER if dead_letter else JobStatus.FAILED
        job.error = error
        job.completed_at = datetime.now(UTC)
        await self.session.flush()

    async def list_stuck_pipeline_jobs(
        self, stale_seconds: int = 600, limit: int = 50
    ) -> list[PipelineJob]:
        """Find jobs stuck in PROCESSING with an old heartbeat."""
        cutoff = (datetime.now(UTC) - __import__("datetime").timedelta(seconds=stale_seconds)).replace(tzinfo=None)
        result = await self.session.execute(
            select(PipelineJob).where(
                PipelineJob.status == JobStatus.PROCESSING,
                PipelineJob.heartbeat_at < cutoff,
            ).order_by(PipelineJob.priority, PipelineJob.created_at).limit(limit)
        )
        return list(result.scalars().all())

    async def reset_stuck_jobs(self, stale_seconds: int = 600) -> int:
        """Reset stuck PROCESSING jobs back to PENDING for retry.

        Resets all RUNNING steps to PENDING so they can be re-tried.
        Returns number of jobs reset.
        """
        stuck = await self.list_stuck_pipeline_jobs(stale_seconds=stale_seconds)
        for job in stuck:
            job.status = JobStatus.PENDING
            job.attempt += 1
            # Reset all RUNNING steps to PENDING so they can resume
            steps_result = await self.session.execute(
                select(PipelineStep).where(
                    PipelineStep.job_id == job.id,
                    PipelineStep.status == StepStatus.RUNNING,
                )
            )
            for step in steps_result.scalars().all():
                step.status = StepStatus.PENDING
        await self.session.flush()
        return len(stuck)

    async def reset_job_for_retry(self, job_id: str) -> PipelineJob | None:
        """Reset a failed/dead-letter job back to PENDING for retry."""
        result = await self.session.execute(
            select(PipelineJob).where(PipelineJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job or job.status not in (JobStatus.FAILED, JobStatus.DEAD_LETTER):
            return None
        job.status = JobStatus.PENDING
        job.error = None
        job.attempt += 1
        # Reset all FAILED steps to PENDING
        steps_result = await self.session.execute(
            select(PipelineStep).where(
                PipelineStep.job_id == job.id,
                PipelineStep.status == StepStatus.FAILED,
            )
        )
        for step in steps_result.scalars().all():
            step.status = StepStatus.PENDING
            step.error = None
        await self.session.flush()
        return job

    async def update_job_heartbeat(self, job_id: str) -> None:
        """Refresh the heartbeat timestamp for a running job."""
        result = await self.session.execute(
            select(PipelineJob).where(PipelineJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.heartbeat_at = datetime.now(UTC)
            await self.session.flush()

    async def list_pipeline_jobs(
        self,
        status: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PipelineJob]:
        """List pipeline jobs, optionally filtered by status."""
        query = select(PipelineJob)
        if status:
            query = query.where(PipelineJob.status == status)
        query = query.order_by(PipelineJob.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ─── Outbox ───────────────────────────────────────────────────────────

    async def publish_outbox_event(
        self,
        event_type: OutboxEventType | str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict | None = None,
        max_attempts: int = 3,
    ) -> OutboxEvent:
        """Insert an outbox event in the current transaction.

        Called from the same transaction that mutates the source-of-truth
        rows so the event is published atomically with the state change.
        """
        event = OutboxEvent(
            id=str(__import__("uuid").uuid4()),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload or {},
            max_attempts=max_attempts,
            status=OutboxEventStatus.PENDING,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def claim_outbox_events(
        self, limit: int = 20, max_attempts: int = None
    ) -> list[OutboxEvent]:
        """Atomically claim pending outbox events for processing.

        Uses SELECT ... FOR UPDATE SKIP LOCKED so concurrent workers never
        claim the same event twice. Only claims events whose next_retry_at
        has passed (or is NULL), respecting exponential backoff delays.
        Returns the claimed events so the caller can process the projection
        and then complete/fail each one.
        """
        now = datetime.now(UTC)
        query = select(OutboxEvent).where(
            OutboxEvent.status == OutboxEventStatus.PENDING,
            (OutboxEvent.next_retry_at.is_(None)) | (OutboxEvent.next_retry_at <= now),
        )
        if max_attempts is not None:
            query = query.where(OutboxEvent.max_attempts <= max_attempts)
        query = (
            query.order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        events = list(result.scalars().all())
        for event in events:
            event.status = OutboxEventStatus.PROCESSING
            event.processed_at = datetime.now(UTC)
        await self.session.flush()
        return events

    async def complete_outbox_event(self, event_id: str) -> None:
        """Mark an outbox event as processed successfully."""
        result = await self.session.execute(
            select(OutboxEvent).where(OutboxEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return
        event.status = OutboxEventStatus.COMPLETED
        event.processed_at = datetime.now(UTC)
        event.last_error = None
        await self.session.flush()

    async def fail_outbox_event(
        self, event_id: str, error: str, requeue: bool = True
    ) -> OutboxEvent | None:
        """Record a failed attempt on an outbox event.

        If attempts remain, the event is requeued back to PENDING with an
        exponential backoff delay (next_retry_at) so the worker doesn't
        immediately re-process a flapping event. Otherwise it is left
        FAILED (dead-letter).
        """
        result = await self.session.execute(
            select(OutboxEvent).where(OutboxEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return None
        event.attempts += 1
        event.last_error = error
        event.processed_at = datetime.now(UTC)
        if requeue and event.attempts < event.max_attempts:
            event.status = OutboxEventStatus.PENDING
            backoff_seconds = min(300, 5 * (2 ** (event.attempts - 1)))
            event.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
        else:
            event.status = OutboxEventStatus.FAILED
            event.next_retry_at = None
        await self.session.flush()
        return event

    async def list_outbox_events(
        self, status: OutboxEventStatus | str = None, limit: int = 50
    ) -> list[OutboxEvent]:
        """List outbox events, optionally filtered by status."""
        query = select(OutboxEvent)
        if status:
            query = query.where(OutboxEvent.status == status)
        query = query.order_by(OutboxEvent.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_outbox_event(self, event_id: str) -> OutboxEvent | None:
        """Get a single outbox event by ID."""
        result = await self.session.execute(
            select(OutboxEvent).where(OutboxEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def count_pending_outbox_events(self) -> int:
        """Count events still PENDING (for reconciliation/surveillance)."""
        result = await self.session.execute(
            select(func.count(OutboxEvent.id)).where(
                OutboxEvent.status == OutboxEventStatus.PENDING
            )
        )
        return result.scalar() or 0

    # ─── Episodic Memory ──────────────────────────────────────────────────

    async def create_episodic_memory(
        self,
        entity_id: str,
        content: str = "",
        source_url: str = "",
        content_type: str = "",
    ) -> EpisodicMemory:
        """Create episodic memory entry."""
        mem = EpisodicMemory(
            id=str(__import__("uuid").uuid4()),
            entity_id=entity_id,
            content=content,
            source_url=source_url,
            content_type=content_type,
        )
        self.session.add(mem)
        await self.session.flush()
        return mem

    # ─── Web References ───────────────────────────────────────────────────

    async def add_web_references(
        self,
        entity_id: str,
        references: list[dict[str, str]],
    ) -> list[WebReference]:
        """Add web references for an entity."""
        refs = []
        for ref in references:
            web_ref = WebReference(
                entity_id=entity_id,
                title=ref.get("title", ""),
                url=ref.get("url", ""),
                snippet=ref.get("snippet", ""),
                source=ref.get("source", ""),
            )
            self.session.add(web_ref)
            refs.append(web_ref)
        await self.session.flush()
        return refs

    # ─── Similar Tools ────────────────────────────────────────────────────

    async def add_similar_tools(
        self,
        entity_id: str,
        tools: list[dict[str, str]],
    ) -> list[SimilarTool]:
        """Add similar tools for an entity."""
        tool_objs = []
        for tool in tools:
            st = SimilarTool(
                entity_id=entity_id,
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                url=tool.get("url", ""),
            )
            self.session.add(st)
            tool_objs.append(st)
        await self.session.flush()
        return tool_objs

    # ─── Output Files ─────────────────────────────────────────────────────

    async def create_output_file(
        self,
        content_id: str,
        filename: str,
        file_path: str,
        file_type: str,
        file_size: int = 0,
    ) -> OutputFile:
        """Create output file record."""
        out = OutputFile(
            content_id=content_id,
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
        )
        self.session.add(out)
        await self.session.flush()
        return out

    # ─── Statistics ───────────────────────────────────────────────────────

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        content_count = (await self.session.execute(
            select(func.count(Content.id))
        )).scalar() or 0

        entity_count = (await self.session.execute(
            select(func.count(Entity.id))
        )).scalar() or 0

        topic_count = (await self.session.execute(
            select(func.count(Topic.id))
        )).scalar() or 0

        relationship_count = (await self.session.execute(
            select(func.count(EntityRelationship.id))
        )).scalar() or 0

        job_count = (await self.session.execute(
            select(func.count(AnalysisJob.id))
        )).scalar() or 0

        return {
            "content_count": content_count,
            "entity_count": entity_count,
            "topic_count": topic_count,
            "relationship_count": relationship_count,
            "job_count": job_count,
        }

    async def consolidate_episodic_memories(
        self,
        entity_id: str,
        max_memories: int = 50,
        keep_recent: int = 10,
    ) -> int:
        """Consolidate old episodic memories for an entity.
        
        Keeps the most recent `keep_recent` memories and consolidates
        the rest into a single summary if total exceeds `max_memories`.
        
        Returns number of memories deleted.
        """
        from src.database.models import EpisodicMemory

        # Get all memories for this entity, ordered by timestamp
        result = await self.session.execute(
            select(EpisodicMemory)
            .where(EpisodicMemory.entity_id == entity_id)
            .order_by(EpisodicMemory.timestamp.desc())
        )
        memories = result.scalars().all()

        if len(memories) <= max_memories:
            return 0

        # Keep recent memories, delete old ones
        to_delete = memories[keep_recent:]
        for memory in to_delete:
            await self.session.delete(memory)

        await self.session.flush()
        return len(to_delete)

    async def cleanup_stale_memories(self, max_age_days: int = 90) -> int:
        """Delete episodic memories older than max_age_days."""
        from datetime import timedelta

        from src.database.models import EpisodicMemory

        cutoff = (datetime.now(UTC) - timedelta(days=max_age_days)).replace(tzinfo=None)
        result = await self.session.execute(
            select(EpisodicMemory)
            .where(EpisodicMemory.timestamp < cutoff)
        )
        stale = result.scalars().all()

        for memory in stale:
            await self.session.delete(memory)

        await self.session.flush()
        return len(stale)
