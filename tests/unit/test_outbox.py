"""Unit tests for the transactional outbox worker and idempotent projection.

These tests use fakes (no Postgres/Neo4j/Qdrant needed) to verify:
- Projection payload → stable Neo4j node id (entity-<pg-id>).
- Re-applying the same event converges (idempotent).
- The worker claims, applies, and completes events; failures are recorded.
- Exponential backoff sets next_retry_at on retryable failures.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.database.models import OutboxEvent, OutboxEventStatus, OutboxEventType
from src.pipeline.outbox import (
    OutboxProjector,
    OutboxWorker,
    build_entity_payload,
    entity_node_id,
)


class FakeGraphStore:
    """Records project calls and can simulate a missing node."""

    def __init__(self):
        self.entities: dict[str, dict[str, Any]] = {}
        self.relationships: list[tuple] = []
        self.deleted: list[str] = []
        self.fail_entities: set[str] = set()

    async def project_entity(self, entity_id: str, payload: dict, embedding=None) -> str:
        if entity_id in self.fail_entities:
            raise RuntimeError("simulated projection failure")
        node_id = entity_node_id(entity_id)
        self.entities[node_id] = payload
        return node_id

    async def project_relationship(self, source_name, target_name, rel_type,
                                   description="", confidence=0.0):
        self.relationships.append((source_name, target_name, rel_type))

    async def project_entity_delete(self, node_id, qdrant_id):
        self.deleted.append(node_id)
        self.entities.pop(node_id, None)

    async def node_exists(self, node_id: str) -> bool:
        return node_id in self.entities


class FakeVectorStore:
    def __init__(self):
        self.points: dict[str, dict] = {}
        self.chunk_count = 0
        self.deleted_urls: list[str] = []

    def point_exists(self, point_id: str) -> bool:
        return point_id in self.points

    def upsert_chunks(self, chunks, source_url: str):
        self.chunk_count += len(chunks)
        for c in chunks:
            self.points[c.id] = {"text": c.text, "source_url": source_url}

    def delete_by_source_url(self, source_url: str):
        self.deleted_urls.append(source_url)
        self.points = {k: v for k, v in self.points.items() if v.get("source_url") != source_url}


def make_event(
    event_type: OutboxEventType,
    aggregate_id: str,
    payload: dict,
    event_id: str = None,
) -> OutboxEvent:
    return OutboxEvent(
        id=event_id or "evt-1",
        event_type=event_type,
        aggregate_type="entity",
        aggregate_id=aggregate_id,
        payload=payload,
        status=OutboxEventStatus.PENDING,
        attempts=0,
        max_attempts=3,
    )


class FakeCrud:
    def __init__(self):
        self.claimed: list[OutboxEvent] = []
        self.completed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.events: dict[str, OutboxEvent] = {}
        self.session = _FakeSession()

    def queue(self, event: OutboxEvent):
        self.claimed.append(event)
        self.events[event.id] = event

    async def claim_outbox_events(self, limit=20, max_attempts=None):
        batch = self.claimed[:limit]
        self.claimed = self.claimed[limit:]
        for e in batch:
            e.status = OutboxEventStatus.PROCESSING
        return batch

    async def complete_outbox_event(self, event_id: str) -> None:
        self.completed.append(event_id)
        if event_id in self.events:
            self.events[event_id].status = OutboxEventStatus.COMPLETED

    async def fail_outbox_event(self, event_id: str, error: str, requeue: bool = True):
        self.failed.append((event_id, error))
        if event_id in self.events:
            event = self.events[event_id]
            event.attempts += 1
            event.last_error = error
            if requeue and event.attempts < event.max_attempts:
                event.status = OutboxEventStatus.PENDING
                backoff_seconds = min(300, 5 * (2 ** (event.attempts - 1)))
                event.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
            else:
                event.status = OutboxEventStatus.FAILED
                event.next_retry_at = None
            return event
        return None


class _FakeSession:
    async def flush(self):
        return None

    async def commit(self):
        return None


def test_entity_node_id_is_deterministic():
    assert entity_node_id("abc-123") == "entity-abc-123"
    assert entity_node_id("abc-123") == entity_node_id("abc-123")


@pytest.mark.asyncio
async def test_project_entity_upsert_uses_stable_id():
    graph = FakeGraphStore()
    vector = FakeVectorStore()
    projector = OutboxProjector(graph, vector)

    event = make_event(
        OutboxEventType.ENTITY_UPSERT,
        aggregate_id="ent-1",
        payload={
            "entity_id": "ent-1",
            "name": "Docker",
            "type": "platform",
            "description": "Containers",
        },
    )
    await projector.apply(event)

    assert "entity-ent-1" in graph.entities
    assert graph.entities["entity-ent-1"]["name"] == "Docker"


@pytest.mark.asyncio
async def test_reapplying_entity_event_is_idempotent():
    graph = FakeGraphStore()
    vector = FakeVectorStore()
    projector = OutboxProjector(graph, vector)

    payload = {
        "entity_id": "ent-1",
        "name": "Docker",
        "type": "platform",
        "description": "Containers",
    }
    for _ in range(3):
        await projector.apply(make_event(OutboxEventType.ENTITY_UPSERT, "ent-1", payload))

    assert len(graph.entities) == 1  # no duplicates


@pytest.mark.asyncio
async def test_worker_drains_and_completes_events():
    graph = FakeGraphStore()
    vector = FakeVectorStore()
    crud = FakeCrud()
    worker = OutboxWorker(crud, OutboxProjector(graph, vector), batch_size=10)

    for i in range(5):
        crud.queue(make_event(
            OutboxEventType.ENTITY_UPSERT,
            f"ent-{i}",
            {"entity_id": f"ent-{i}", "name": f"E{i}", "type": "tool"},
            event_id=f"evt-{i}",
        ))

    summary = await worker.drain()

    assert summary == {"processed": 5, "failed": 0, "completed": 5}
    assert len(graph.entities) == 5
    assert len(crud.completed) == 5


@pytest.mark.asyncio
async def test_worker_records_failures():
    graph = FakeGraphStore()
    vector = FakeVectorStore()
    graph.fail_entities.add("ent-bad")
    crud = FakeCrud()
    worker = OutboxWorker(crud, OutboxProjector(graph, vector), batch_size=10)

    crud.queue(make_event(
        OutboxEventType.ENTITY_UPSERT,
        "ent-ok",
        {"entity_id": "ent-ok", "name": "OK", "type": "tool"},
        event_id="evt-ok",
    ))
    crud.queue(make_event(
        OutboxEventType.ENTITY_UPSERT,
        "ent-bad",
        {"entity_id": "ent-bad", "name": "BAD", "type": "tool"},
        event_id="evt-bad",
    ))

    summary = await worker.drain()

    assert summary["processed"] == 2
    assert summary["failed"] == 1
    assert summary["completed"] == 1
    assert len(crud.failed) == 1
    assert crud.failed[0][0] == "evt-bad"


@pytest.mark.asyncio
async def test_worker_projects_relationships_and_chunks():
    graph = FakeGraphStore()
    vector = FakeVectorStore()
    projector = OutboxProjector(graph, vector)
    crud = FakeCrud()
    worker = OutboxWorker(crud, projector, batch_size=10)

    crud.queue(make_event(
        OutboxEventType.RELATIONSHIP_UPSERT,
        "rel-1",
        {"source": "Docker", "target": "Kubernetes", "relation_type": "ORCHESTRATES"},
        event_id="evt-rel",
    ))
    crud.queue(make_event(
        OutboxEventType.CONTENT_CHUNKS_UPSERT,
        "content-1",
        {"source_url": "https://example.com/v", "chunks": [
            {"id": "chunk-1", "text": "hello", "chunk_index": 0, "token_count": 5,
             "embedding": [0.1, 0.2], "metadata": {"k": "v"}},
        ]},
        event_id="evt-chunk",
    ))

    summary = await worker.drain()

    assert summary["completed"] == 2
    assert graph.relationships == [("Docker", "Kubernetes", "ORCHESTRATES")]
    assert vector.chunk_count == 1
    assert "chunk-1" in vector.points


def test_build_entity_payload_handles_enum_type():
    from src.database.models import EntityType as DbEntityType

    class FakeEntityType:
        name = DbEntityType.PLATFORM.value

    class FakeEntity:
        id = "e-1"
        name = "Docker"
        entity_type = FakeEntityType()
        description = "Containers"
        summary = ""
        key_points = []
        confidence = 0.9
        version = 2
        source_url = None
        source_chunk_id = None

    payload = build_entity_payload(FakeEntity())
    assert payload["entity_id"] == "e-1"
    assert payload["type"] == "platform"
    assert payload["confidence"] == 0.9
    assert "entity_id" in payload and "source_url" not in payload  # None stripped


@pytest.mark.asyncio
async def test_fail_outbox_event_sets_backoff():
    """First retryable failure should set next_retry_at ~5s in the future."""
    crud = FakeCrud()
    event = make_event(
        OutboxEventType.ENTITY_UPSERT,
        aggregate_id="ent-1",
        payload={"entity_id": "ent-1", "name": "X", "type": "tool"},
        event_id="evt-backoff",
    )
    crud.queue(event)

    result = await crud.fail_outbox_event("evt-backoff", "simulated error", requeue=True)

    assert result is not None
    assert result.status == OutboxEventStatus.PENDING
    assert result.attempts == 1
    assert result.next_retry_at is not None
    delta = result.next_retry_at - datetime.now(UTC)
    assert 4.0 < delta.total_seconds() < 8.0  # ~5s backoff


@pytest.mark.asyncio
async def test_fail_outbox_event_doubles_backoff():
    """Second retryable failure should double the backoff (~10s)."""
    crud = FakeCrud()
    event = make_event(
        OutboxEventType.ENTITY_UPSERT,
        aggregate_id="ent-1",
        payload={"entity_id": "ent-1", "name": "X", "type": "tool"},
        event_id="evt-backoff2",
    )
    crud.queue(event)

    await crud.fail_outbox_event("evt-backoff2", "error 1", requeue=True)
    result = await crud.fail_outbox_event("evt-backoff2", "error 2", requeue=True)

    assert result.attempts == 2
    assert result.status == OutboxEventStatus.PENDING
    delta = result.next_retry_at - datetime.now(UTC)
    assert 9.0 < delta.total_seconds() < 13.0  # ~10s backoff


@pytest.mark.asyncio
async def test_fail_outbox_event_dead_letters_on_max_attempts():
    """Exhausting max_attempts should set status to FAILED with no next_retry_at."""
    crud = FakeCrud()
    event = make_event(
        OutboxEventType.ENTITY_UPSERT,
        aggregate_id="ent-1",
        payload={"entity_id": "ent-1", "name": "X", "type": "tool"},
        event_id="evt-dead",
    )
    event.max_attempts = 2
    crud.queue(event)

    await crud.fail_outbox_event("evt-dead", "error 1", requeue=True)
    result = await crud.fail_outbox_event("evt-dead", "error 2", requeue=True)

    assert result.attempts == 2
    assert result.status == OutboxEventStatus.FAILED
    assert result.next_retry_at is None
