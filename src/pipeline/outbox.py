"""Transactional outbox worker.

PostgreSQL is the canonical source of truth. When an entity/relationship/
content changes, an outbox event is inserted in the SAME transaction as the
state change (see CRUDOperations.publish_outbox_event). This worker claims
pending events and rebuilds the derived Neo4j/Qdrant projections idempotently
using stable IDs, so re-processing never creates duplicates.

Design goals (Phase 1, item 2/4):
- Outbox events are durable: they live in PG, committed atomically with the
  source-of-truth write.
- Projections are idempotent: Neo4j nodes are MERGE'd by a deterministic id
  (`entity-<pg-id>`), Qdrant points use the PG entity id as the point id.
- Workers retry with bounded attempts, then leave the event FAILED (dead-letter)
  for reconciliation to inspect.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger

from src.database.crud import CRUDOperations
from src.database.models import OutboxEvent, OutboxEventType


def entity_node_id(entity_id: str) -> str:
    """Deterministic Neo4j node id derived from the PG entity id."""
    return f"entity-{entity_id}"


def build_entity_payload(entity, item: dict | None = None) -> dict:
    """Serialize a PG Entity (plus optional projection extras) into an outbox payload."""
    payload = {
        "entity_id": entity.id,
        "name": entity.name,
        "type": entity.entity_type.name if entity.entity_type else "unknown",
        "description": entity.description or "",
        "summary": entity.summary or "",
        "key_points": entity.key_points or [],
        "confidence": entity.confidence or 0.0,
        "version": entity.version or 1,
        "source_url": entity.source_url if hasattr(entity, "source_url") else None,
        "source_chunk_id": entity.source_chunk_id if hasattr(entity, "source_chunk_id") else None,
        "tags": (item or {}).get("tags", []),
        "topic": (item or {}).get("topic"),
        "sub_topic": (item or {}).get("sub_topic"),
        "content_type": (item or {}).get("content_type"),
        "web_info": (item or {}).get("web_info", []),
        "similar_tools": (item or {}).get("similar_tools", []),
    }
    return {k: v for k, v in payload.items() if v is not None}


class OutboxProjector:
    """Applies a single outbox event to Neo4j/Qdrant idempotently.

    Wraps the graph store and vector store. Every handler is designed so that
    applying the same event twice converges to the same state.
    """

    def __init__(self, graph_store, vector_store, embedder=None):
        self.graph_store = graph_store
        self.vector_store = vector_store
        self.embedder = embedder

    async def apply(self, event: OutboxEvent) -> None:
        """Dispatch an event to the appropriate idempotent handler."""
        handler = self._handlers().get(event.event_type)
        if handler is None:
            raise ValueError(f"Unknown outbox event type: {event.event_type}")
        await handler(event.payload or {})

    def _handlers(self) -> dict[OutboxEventType, Callable[[dict], Awaitable[None]]]:
        return {
            OutboxEventType.ENTITY_UPSERT: self._project_entity_upsert,
            OutboxEventType.ENTITY_DELETE: self._project_entity_delete,
            OutboxEventType.RELATIONSHIP_UPSERT: self._project_relationship_upsert,
            OutboxEventType.CONTENT_CHUNKS_UPSERT: self._project_content_chunks_upsert,
            OutboxEventType.CONTENT_DELETE: self._project_content_delete,
        }

    async def _project_entity_upsert(self, payload: dict) -> None:
        entity_id = payload["entity_id"]
        node_id = await self.graph_store.project_entity(entity_id, payload)
        logger.info(f"Projected entity '{payload.get('name')}' -> {node_id}")

    async def _project_entity_delete(self, payload: dict) -> None:
        node_id = payload.get("node_id") or entity_node_id(payload["entity_id"])
        qdrant_id = payload.get("qdrant_id") or payload.get("entity_id")
        await self.graph_store.project_entity_delete(node_id, qdrant_id)
        logger.info(f"Deleted projection for {node_id}")

    async def _project_relationship_upsert(self, payload: dict) -> None:
        await self.graph_store.project_relationship(
            source_name=payload["source"],
            target_name=payload["target"],
            rel_type=payload["relation_type"],
            description=payload.get("description", ""),
            confidence=payload.get("confidence", 0.0),
        )
        logger.info(
            f"Projected relationship {payload['source']} "
            f"-[{payload['relation_type']}]-> {payload['target']}"
        )

    async def _project_content_chunks_upsert(self, payload: dict) -> None:
        chunks = payload.get("chunks", [])
        if not chunks:
            return
        # Rehydrate DocumentChunk-like objects minimally for the vector store.
        from src.config.models import DocumentChunk

        hydrated = []
        for c in chunks:
            chunk = DocumentChunk(
                id=c["id"],
                text=c.get("text", ""),
                chunk_index=c.get("chunk_index", 0),
                token_count=c.get("token_count", 0),
            )
            chunk.embedding = c.get("embedding")
            chunk.metadata = c.get("metadata", {})
            hydrated.append(chunk)
        self.vector_store.upsert_chunks(hydrated, payload.get("source_url", ""))
        logger.info(f"Projected {len(hydrated)} content chunks for {payload.get('source_url')}")

    async def _project_content_delete(self, payload: dict) -> None:
        source_url = payload.get("source_url")
        if source_url:
            self.vector_store.delete_by_source_url(source_url)
        logger.info(f"Deleted content projection for {source_url}")


class OutboxWorker:
    """Claims pending outbox events and applies them via a projector.

    The worker is deliberately simple: a single `drain()` call processes all
    currently-pending events (used synchronously after a pipeline run), and
    `run_forever()` provides the background loop for a standalone worker.
    """

    def __init__(
        self,
        crud: CRUDOperations,
        projector: OutboxProjector,
        batch_size: int = 20,
    ):
        self.crud = crud
        self.projector = projector
        self.batch_size = batch_size

    async def drain(self, max_events: int = 500) -> dict[str, int]:
        """Process all currently-pending events.

        Returns a summary dict like {"processed": n, "failed": n, "completed": n}.
        """
        summary = {"processed": 0, "failed": 0, "completed": 0}
        claimed = await self.crud.claim_outbox_events(limit=self.batch_size)
        processed_this_batch = 0

        while claimed and processed_this_batch < max_events:
            for event in claimed:
                try:
                    await self.projector.apply(event)
                except Exception as e:
                    logger.error(f"Outbox event {event.id} failed: {e}")
                    await self.crud.fail_outbox_event(event.id, str(e))
                    summary["failed"] += 1
                else:
                    await self.crud.complete_outbox_event(event.id)
                    summary["completed"] += 1
                summary["processed"] += 1
                processed_this_batch += 1

            await self.crud.session.flush()
            if processed_this_batch >= max_events:
                break
            claimed = await self.crud.claim_outbox_events(limit=self.batch_size)

        return summary

    async def run_forever(
        self,
        poll_interval: float = 5.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Background loop for a long-running worker process."""
        stop = stop_event or asyncio.Event()
        logger.info("Outbox worker started")
        while not stop.is_set():
            try:
                summary = await self.drain()
                if summary["processed"]:
                    logger.info(f"Outbox drain: {summary}")
            except Exception as e:
                logger.error(f"Outbox worker error: {e}")
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
            except TimeoutError:
                continue


def build_projector(graph_store, vector_store, embedder=None) -> OutboxProjector:
    """Construct a projector wired to the live graph/vector stores."""
    return OutboxProjector(
        graph_store=graph_store,
        vector_store=vector_store,
        embedder=embedder,
    )


async def persist_and_publish(
    crud: CRUDOperations,
    content_id: str,
    categorized,
    relationships,
    chunks=None,
    pipeline_version: str = "0.3.0",
    model_version: str = None,
    embedding_version: str = None,
) -> dict[str, int]:
    """Persist pipeline results to PG (source of truth) and publish outbox events.

    Runs entirely in the caller's transaction (the same session that claims
    the job / writes the content row), so the state change and its outbox
    events commit atomically. Returns counts: {"entities": n, "relationships": n}.

    Args:
        crud: CRUDOperations bound to the current session.
        content_id: PG content id the entities belong to.
        categorized: list[CategorizedItem] from the pipeline.
        relationships: list[ExtractedRelationship] from the pipeline.
        chunks: optional list[DocumentChunk] (embeddings reused for the vector
            projection so we never re-embed).
        pipeline_version: version string for provenance tracking.
        model_version: LLM model version used for extraction.
        embedding_version: embedding model version used for vectors.
    """
    counts = {"entities": 0, "relationships": 0, "chunks": 0}
    from datetime import datetime, UTC

    # 1. Persist entities (get-or-create by name, per source-of-truth rule).
    #    Uses FOR UPDATE locking to prevent concurrent workers from creating
    #    duplicate entities when two pipelines process the same entity name.
    for item in categorized:
        e = item.entity
        etype = e.type.value if hasattr(e.type, "value") else str(e.type)
        existing = await crud.get_entity_by_name_for_update(e.name)
        if existing:
            entity = existing
        else:
            entity = await crud.create_entity(
                name=e.name,
                entity_type=etype,
                description=e.description,
                confidence=e.confidence,
                extraction_timestamp=datetime.now(UTC),
                pipeline_version=pipeline_version,
                model_version=model_version,
                embedding_version=embedding_version,
            )
        await crud.link_content_entity(
            content_id=content_id,
            entity_id=entity.id,
            relevance=item.topic_confidence,
        )

        payload = {
            "entity_id": entity.id,
            "name": entity.name,
            "type": etype,
            "description": entity.description or e.description,
            "summary": item.summary or "",
            "key_points": item.key_points,
            "confidence": entity.confidence or e.confidence,
            "version": entity.version,
            "source_url": (e.source_url if hasattr(e, "source_url") else None),
            "source_chunk_id": (e.source_chunk_id if hasattr(e, "source_chunk_id") else None),
            "tags": item.tags,
            "topic": item.primary_topic.value,
            "sub_topic": item.sub_topics[0] if item.sub_topics else None,
            "content_type": item.content_type.value,
            "web_info": [
                w.model_dump() if hasattr(w, "model_dump") else dict(w)
                for w in e.web_info
            ],  # type: ignore[attr-defined]
            "similar_tools": [
                t.model_dump() if hasattr(t, "model_dump") else dict(t)
                for t in e.similar_tools
            ],  # type: ignore[attr-defined]
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        await crud.publish_outbox_event(
            event_type=OutboxEventType.ENTITY_UPSERT,
            aggregate_type="entity",
            aggregate_id=entity.id,
            payload=payload,
        )
        counts["entities"] += 1

    # 2. Persist relationships + publish projection events.
    for rel in relationships:
        source = await crud.get_entity_by_name(rel.source)
        target = await crud.get_entity_by_name(rel.target)
        if source and target:
            rel_type = (
                rel.relation_type.upper()
                if isinstance(rel.relation_type, str)
                else rel.relation_type.value
            )
            await crud.create_entity_relationship(
                source_entity_id=source.id,
                target_entity_id=target.id,
                relationship_type=rel_type,
                description=rel.description,
                confidence=rel.confidence,
                source_content_id=content_id,
            )
            await crud.publish_outbox_event(
                event_type=OutboxEventType.RELATIONSHIP_UPSERT,
                aggregate_type="relationship",
                aggregate_id=f"{source.id}->{target.id}",
                payload={
                    "source": rel.source,
                    "target": rel.target,
                    "relation_type": rel_type,
                    "description": rel.description,
                    "confidence": rel.confidence,
                },
            )
            counts["relationships"] += 1

    # 3. Publish content-chunk projection (embeddings carried over from the pipeline).
    if chunks:
        chunk_payloads = []
        for c in chunks:
            chunk_payloads.append({
                "id": c.id,
                "text": c.text,
                "chunk_index": c.chunk_index,
                "token_count": c.token_count,
                "embedding": c.embedding,
                "metadata": c.metadata,
            })
        await crud.publish_outbox_event(
            event_type=OutboxEventType.CONTENT_CHUNKS_UPSERT,
            aggregate_type="content",
            aggregate_id=content_id,
            payload = {
            "source_url": (
                str(getattr(relationships[0], "source", "")) if relationships else ""
            ),
            "chunks": chunk_payloads,
        }
        )
        counts["chunks"] = len(chunk_payloads)

    return counts
