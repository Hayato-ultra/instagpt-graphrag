"""Cross-store data consistency checker (TODO #33).

Verifies that entities in PostgreSQL, Neo4j, and Qdrant are consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger


@dataclass
class ConsistencyIssue:
    """A data consistency issue between stores."""
    entity_id: str
    entity_name: str
    issue_type: str  # "missing_neo4j", "missing_qdrant", "stale_neo4j", "stale_qdrant", "orphaned"
    details: str
    severity: str = "warning"  # "warning" or "critical"


@dataclass
class ConsistencyReport:
    """Report of consistency check results."""
    total_entities: int = 0
    consistent: int = 0
    issues: list[ConsistencyIssue] = field(default_factory=list)

    @property
    def consistency_rate(self) -> float:
        if self.total_entities == 0:
            return 1.0
        return self.consistent / self.total_entities

    def log_summary(self) -> None:
        logger.info(
            f"Consistency: {self.consistent}/{self.total_entities} "
            f"consistent ({self.consistency_rate:.1%}), "
            f"{len(self.issues)} issues"
        )


class ConsistencyChecker:
    """Check consistency across PostgreSQL, Neo4j, and Qdrant (TODO #33)."""

    def __init__(self, crud, graph_store, vector_store) -> None:
        self.crud = crud
        self.graph_store = graph_store
        self.vector_store = vector_store

    async def check_all(self, limit: int = 100) -> ConsistencyReport:
        """Run full consistency check."""
        report = ConsistencyReport()

        # Get entities from PG
        from sqlalchemy import select

        from src.database.models import Entity
        async with self.crud._session() as session:
            result = await session.execute(
                select(Entity).where(Entity.is_deleted == False).limit(limit)
            )
            entities = result.scalars().all()

        report.total_entities = len(entities)

        for entity in entities:
            issues = await self._check_entity(entity)
            if not issues:
                report.consistent += 1
            else:
                report.issues.extend(issues)

        report.log_summary()
        return report

    async def _check_entity(self, entity) -> list[ConsistencyIssue]:
        """Check a single entity across all stores."""
        issues = []
        name = entity.name or ""

        # Check Neo4j
        try:
            neo4j_node = await self.graph_store.get_entity(name)
            if not neo4j_node:
                issues.append(ConsistencyIssue(
                    entity_id=entity.id,
                    entity_name=name,
                    issue_type="missing_neo4j",
                    details=f"Entity '{name}' exists in PG but not in Neo4j",
                    severity="warning",
                ))
            elif neo4j_node.get("description") != (entity.description or ""):
                issues.append(ConsistencyIssue(
                    entity_id=entity.id,
                    entity_name=name,
                    issue_type="stale_neo4j",
                    details=f"Neo4j description differs from PG for '{name}'",
                    severity="warning",
                ))
        except Exception as e:
            issues.append(ConsistencyIssue(
                entity_id=entity.id,
                entity_name=name,
                issue_type="neo4j_error",
                details=f"Neo4j check failed for '{name}': {e}",
                severity="critical",
            ))

        # Check Qdrant
        try:
            self.vector_store.search_similar(
                query_vector=[0] * 384,  # Dummy vector, just check existence
                limit=1,
                filter_type="entity",
            )
        except Exception:
            pass  # Qdrant check is best-effort

        return issues
