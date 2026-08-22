"""Unit tests for reconciliation (drift detection/repair) without live stores.

Uses fake graph/vector stores plus an in-memory CRUD stub to verify:
- Missing-node and missing-point drift are detected.
- Repair re-publishes an outbox event and replays the projection.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.database.models import OutboxEventType
from src.pipeline.outbox import OutboxProjector, entity_node_id


class FakeEntity:
    def __init__(self, eid: str, name: str, version: int = 1):
        self.id = eid
        self.name = name
        self.version = version
        self.neo4j_id = None
        self.qdrant_id = None
        self.entity_type = _Type()
        self.description = "desc"
        self.summary = ""
        self.key_points = []
        self.confidence = 0.5
        self.source_url = None
        self.source_chunk_id = None
        self.created_at = None


class _Type:
    name = "tool"


class FakeGraphStore:
    def __init__(self, present: set[str]):
        self.present = present
        self.project_calls: list[str] = []

    async def node_exists(self, node_id: str) -> bool:
        return node_id in self.present

    async def project_entity(self, entity_id, payload, embedding=None):
        self.project_calls.append(entity_id)
        return entity_node_id(entity_id)


class FakeVectorStore:
    def __init__(self, present: set[str]):
        self.present = present
        self.default_present = True

    def point_exists(self, point_id: str) -> bool:
        if not self.default_present:
            return point_id in self.present
        return point_id in self.present


class FakeCrud:
    def __init__(self, entities: list[FakeEntity]):
        self.entities = entities
        self.published: list[dict[str, Any]] = []
        self.session = _Session(entities)

    async def publish_outbox_event(
        self, event_type, aggregate_type, aggregate_id, payload=None, max_attempts=3
    ):
        self.published.append({
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "payload": payload or {},
        })
        return None


class _Session:
    def __init__(self, entities):
        self.entities = entities

    async def execute(self, stmt):
        limit = getattr(stmt, "_limit", None)
        offset = getattr(stmt, "_offset", None) or 0
        page = self.entities[offset:]
        if limit is not None:
            page = page[:limit]
        return _Result(page)

    async def flush(self):
        return None


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return _Scalars(self.rows)

    def scalar_one_or_none(self):
        return None


class _Scalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


def _make_reconciler(entities, graph_present, vector_present, with_projector=True):
    from src.database.reconcile import Reconciler

    crud = FakeCrud(entities)
    graph = FakeGraphStore(graph_present)
    vector = FakeVectorStore(vector_present)
    projector = OutboxProjector(graph, vector) if with_projector else None
    return Reconciler(crud, graph, vector, projector=projector), crud, graph


@pytest.mark.asyncio
async def test_detects_missing_projections():
    entities = [FakeEntity("e-1", "Docker"), FakeEntity("e-2", "Kube")]
    reconciler, _, graph = _make_reconciler(entities, graph_present=set(), vector_present=set())

    result = await reconciler.run(limit=10, repair=False)

    assert result.checked == 2
    assert "Docker" in result.missing_node
    assert "Kube" in result.missing_node
    assert result.repaired == 0


@pytest.mark.asyncio
async def test_repair_republishes_and_replays():
    entities = [FakeEntity("e-1", "Docker")]
    reconciler, crud, graph = _make_reconciler(entities, graph_present=set(), vector_present=set())

    result = await reconciler.run(limit=10, repair=True)

    assert result.repaired == 1
    # One outbox event republished for the repair
    assert len(crud.published) == 1
    assert crud.published[0]["event_type"] == OutboxEventType.ENTITY_UPSERT
    assert crud.published[0]["aggregate_id"] == "e-1"
    # And the projection was replayed immediately
    assert graph.project_calls == ["e-1"]


@pytest.mark.asyncio
async def test_repair_skips_healthy_entities():
    entities = [FakeEntity("e-1", "Docker")]
    reconciler, crud, graph = _make_reconciler(
        entities,
        graph_present={entity_node_id("e-1")},
        vector_present={"e-1"},
    )

    result = await reconciler.run(limit=10, repair=True)

    assert result.checked == 1
    assert result.repaired == 0
    assert crud.published == []
    assert graph.project_calls == []


@pytest.mark.asyncio
async def test_run_reconciliation_wrapper_returns_dict():
    from src.database.reconcile import run_reconciliation

    entities = [FakeEntity("e-1", "Docker")]
    crud = FakeCrud(entities)
    graph = FakeGraphStore(present=set())
    vector = FakeVectorStore(present=set())
    projector = OutboxProjector(graph, vector)

    payload = await run_reconciliation(
        crud, graph, vector, projector=projector, limit=10, repair=True
    )

    assert payload["checked"] == 1
    assert payload["repaired"] == 1
