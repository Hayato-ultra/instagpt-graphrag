"""CRUD operations for the knowledge graph database.

Provides methods to create, read, update, and delete records.
All operations are async and use the SQLAlchemy session.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import (
    Content, ContentChunk, Entity, EntityTypeRow, Topic, SubTopic,
    ContentEntity, ContentTopic, EntityRelationship, EntitySimilarity,
    AnalysisJob, EpisodicMemory, WebReference, SimilarTool, OutputFile,
    ContentType, EntityType, TopicCategory, JobStatus, RelationshipType,
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

    async def get_content_by_url(self, url: str) -> Optional[Content]:
        """Get content by URL."""
        result = await self.session.execute(
            select(Content).where(Content.url == url)
        )
        return result.scalar_one_or_none()

    async def get_content_by_id(self, content_id: str) -> Optional[Content]:
        """Get content by ID."""
        result = await self.session.execute(
            select(Content).where(Content.id == content_id)
        )
        return result.scalar_one_or_none()

    async def list_content(self, limit: int = 100, offset: int = 0) -> List[Content]:
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
    ) -> Optional[Content]:
        """Update content summary after processing."""
        content = await self.get_content_by_id(content_id)
        if content:
            content.summary = summary
            content.entities_count = entities_count
            content.updated_at = datetime.utcnow()
            await self.session.flush()
        return content

    # ─── Content Chunks ───────────────────────────────────────────────────

    async def create_chunks(
        self,
        content_id: str,
        chunks: List[Dict[str, Any]],
    ) -> List[ContentChunk]:
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
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """Get entity by exact name (case-insensitive)."""
        result = await self.session.execute(
            select(Entity).where(func.lower(Entity.name) == func.lower(name))
        )
        return result.scalar_one_or_none()

    async def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        result = await self.session.execute(
            select(Entity).where(Entity.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def search_entities(self, query: str, limit: int = 20) -> List[Entity]:
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
    ) -> Optional[Entity]:
        """Update entity fields."""
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
        entity.updated_at = datetime.utcnow()
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
            existing.updated_at = datetime.utcnow() if hasattr(existing, "updated_at") else None
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
    ) -> List[EntityRelationship]:
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
    ) -> Optional[AnalysisJob]:
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
            job.completed_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def get_job(self, job_id: str) -> Optional[AnalysisJob]:
        """Get analysis job by ID."""
        result = await self.session.execute(
            select(AnalysisJob).where(AnalysisJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(self, limit: int = 100) -> List[AnalysisJob]:
        """List all analysis jobs."""
        result = await self.session.execute(
            select(AnalysisJob)
            .order_by(AnalysisJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

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
        references: List[Dict[str, str]],
    ) -> List[WebReference]:
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
        tools: List[Dict[str, str]],
    ) -> List[SimilarTool]:
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

    async def get_stats(self) -> Dict[str, Any]:
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
