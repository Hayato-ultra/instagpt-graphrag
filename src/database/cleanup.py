"""Graph cleanup job — detects and flags stale, low-confidence, and isolated nodes.

Addresses TODO #35 (Graph Pollution): detects isolated, duplicate, stale,
and low-confidence nodes so they can be pruned or flagged for review.

Runs as a reconciliation step against the PostgreSQL source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import func, select

from src.database.crud import CRUDOperations
from src.database.models import Entity, EntityRelationship


@dataclass
class CleanupResult:
    """Summary of graph cleanup actions."""
    low_confidence: int = 0
    stale: int = 0
    isolated: int = 0
    flagged: list[str] = field(default_factory=list)


async def cleanup_graph(
    crud: CRUDOperations,
    confidence_threshold: float = 0.3,
    stale_days: int = 90,
) -> CleanupResult:
    """Scan entities and flag low-confidence, stale, and isolated nodes.

    - **Low confidence**: entity.confidence < threshold → flag for review.
    - **Stale**: not updated within stale_days → flag for review.
    - **Isolated**: no content_entities AND no relationships → flag for removal.

    Does NOT delete anything — only flags entities via metadata for human review.
    """
    result = CleanupResult()
    cutoff = (datetime.now(UTC) - timedelta(days=stale_days)).replace(tzinfo=None)

    # 1. Flag low-confidence entities
    stmt = select(Entity).where(
        Entity.confidence < confidence_threshold,
        Entity.confidence > 0,  # 0 means validation never ran
    )
    rows = (await crud.session.execute(stmt)).scalars().all()
    result.low_confidence = len(rows)
    for entity in rows:
        meta = entity.metadata_ or {}
        if "_cleanup_flag" not in meta:
            meta["_cleanup_flag"] = "low_confidence"
            meta["_cleanup_at"] = datetime.now(UTC).isoformat()
            entity.metadata_ = meta
            result.flagged.append(f"low_confidence:{entity.name}")

    # 2. Flag stale entities (not updated in stale_days)
    stmt = select(Entity).where(Entity.updated_at < cutoff)
    rows = (await crud.session.execute(stmt)).scalars().all()
    result.stale = len(rows)
    for entity in rows:
        meta = entity.metadata_ or {}
        if "_cleanup_flag" not in meta:
            meta["_cleanup_flag"] = "stale"
            meta["_cleanup_at"] = datetime.now(UTC).isoformat()
            entity.metadata_ = meta
            result.flagged.append(f"stale:{entity.name}")

    # 3. Flag isolated entities (no content links AND no relationships)
    subq_content = (
        select(func.count()).select_from(Entity.content_entities.property.mapper.class_).where(
            Entity.content_entities.property.mapper.class_.entity_id == Entity.id  # type: ignore
        ).correlate(Entity).scalar_subquery()
    )
    subq_rels = (
        select(func.count()).select_from(EntityRelationship).where(
            (EntityRelationship.source_entity_id == Entity.id)
            | (EntityRelationship.target_entity_id == Entity.id)
        ).correlate(Entity).scalar_subquery()
    )
    stmt = select(Entity).where(subq_content == 0, subq_rels == 0)
    rows = (await crud.session.execute(stmt)).scalars().all()
    result.isolated = len(rows)
    for entity in rows:
        meta = entity.metadata_ or {}
        if "_cleanup_flag" not in meta:
            meta["_cleanup_flag"] = "isolated"
            meta["_cleanup_at"] = datetime.now(UTC).isoformat()
            entity.metadata_ = meta
            result.flagged.append(f"isolated:{entity.name}")

    await crud.session.flush()
    logger.info(
        f"Graph cleanup: {result.low_confidence} low-confidence, "
        f"{result.stale} stale, {result.isolated} isolated — "
        f"{len(result.flagged)} entities flagged"
    )
    return result
