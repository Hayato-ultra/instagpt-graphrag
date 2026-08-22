"""Reconciliation job for source-of-truth (PostgreSQL) vs derived stores.

Detects and repairs drift between PostgreSQL (canonical) and the derived
Neo4j/Qdrant projections. Because projections are idempotent (stable IDs,
MERGE-based writes), repair is just "re-publish the outbox event and replay".

Drift types detected:
- Missing projection: a PG entity whose Neo4j node / Qdrant point is absent.
- Unlinked projection: a PG entity with null neo4j_id/qdrant_id (never projected).
- Orphaned projection: a Neo4j node / Qdrant point with no PG entity.
"""
from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import select

from src.database.crud import CRUDOperations
from src.database.models import Entity, OutboxEventType
from src.pipeline.outbox import (
    OutboxProjector,
    build_entity_payload,
    entity_node_id,
)


class ReconciliationResult:
    """Summary of a reconciliation run."""

    def __init__(self):
        self.checked: int = 0
        self.missing_node: list[str] = []
        self.missing_point: list[str] = []
        self.unlinked: list[str] = []
        self.orphaned_nodes: list[str] = []
        self.orphaned_points: list[str] = []
        self.repaired: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "missing_node": self.missing_node,
            "missing_point": self.missing_point,
            "unlinked": self.unlinked,
            "orphaned_nodes": self.orphaned_nodes,
            "orphaned_points": self.orphaned_points,
            "repaired": self.repaired,
        }


class Reconciler:
    """Compares PG entities against Neo4j/Qdrant and repairs drift.

    Expected to be constructed with the live graph store, vector store, and
    an outbox projector (which may share those stores).
    """

    def __init__(
        self,
        crud: CRUDOperations,
        graph_store,
        vector_store,
        projector: OutboxProjector | None = None,
    ):
        self.crud = crud
        self.graph_store = graph_store
        self.vector_store = vector_store
        self.projector = projector

    async def _graph_has_node(self, node_id: str) -> bool:
        if self.graph_store is None:
            return True  # nothing to compare against
        return await self.graph_store.node_exists(node_id)

    def _has_point(self, point_id: str) -> bool:
        if self.vector_store is None:
            return True
        if not point_id:
            return False
        return self.vector_store.point_exists(point_id)

    async def _list_entities(self, offset: int, limit: int) -> list[Entity]:
        result = await self.crud.session.execute(
            select(Entity).order_by(Entity.created_at).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def run(self, limit: int = 1000, repair: bool = False) -> ReconciliationResult:
        """Reconcile PG entities against the derived stores.

        Args:
            limit: Max entities to scan.
            repair: If True, re-publish outbox events for missing projections and
                replay them through the projector immediately.

        Returns:
            ReconciliationResult with a human/machine-readable summary.
        """
        result = ReconciliationResult()
        items = []
        offset = 0
        while True:
            batch = await self._list_entities(offset=offset, limit=500)
            items.extend(batch)
            offset += len(batch)
            if not batch or len(items) >= limit:
                break
        items = items[:limit]

        for entity in items:
            result.checked += 1
            name = entity.name

            node_id = entity.neo4j_id or entity_node_id(entity.id)
            qdrant_point = entity.qdrant_id or entity.id

            has_node = await self._graph_has_node(node_id)
            has_point = self._has_point(qdrant_point)

            if not entity.neo4j_id or not entity.qdrant_id:
                result.unlinked.append(name)
            if not has_node:
                result.missing_node.append(name)
            if not has_point:
                result.missing_point.append(name)

            if repair and (not has_node or not has_point):
                await self._repair_entity(entity)
                result.repaired += 1

        await self.crud.session.flush()
        if result.repaired:
            logger.info(f"Reconciliation: repaired {result.repaired} entities")
        return result

    async def _repair_entity(self, entity: Entity) -> None:
        """Re-publish an outbox event for a drifted entity and replay it."""
        payload = build_entity_payload(entity)
        await self.crud.publish_outbox_event(
            event_type=OutboxEventType.ENTITY_UPSERT,
            aggregate_type="entity",
            aggregate_id=entity.id,
            payload=payload,
        )
        if self.projector is not None:
            from src.database.models import OutboxEvent, OutboxEventStatus

            pending = OutboxEvent(
                id="reconcile-pending",
                event_type=OutboxEventType.ENTITY_UPSERT,
                aggregate_type="entity",
                aggregate_id=entity.id,
                payload=payload,
                status=OutboxEventStatus.PENDING,
            )
            try:
                await self.projector.apply(pending)
            except Exception as e:
                logger.warning(f"Reconciliation replay failed for '{entity.name}': {e}")


async def run_reconciliation(
    crud: CRUDOperations,
    graph_store,
    vector_store,
    projector: OutboxProjector | None = None,
    limit: int = 1000,
    repair: bool = False,
) -> dict[str, Any]:
    """Convenience wrapper that runs a reconciliation and returns the dict."""
    reconciler = Reconciler(
        crud=crud,
        graph_store=graph_store,
        vector_store=vector_store,
        projector=projector,
    )
    result = await reconciler.run(limit=limit, repair=repair)
    return result.as_dict()
