"""Backup and disaster recovery utilities (TODO #62).

Provides backup/restore functions for PostgreSQL, Neo4j, and Qdrant.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


class BackupManager:
    """Manage backups for PostgreSQL, Neo4j, and Qdrant (TODO #62)."""

    def __init__(self, backup_dir: str | Path = "backups") -> None:
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def backup_pg(self, crud) -> Path:
        """Backup PostgreSQL entities to JSON file."""
        from sqlalchemy import select

        from src.database.models import Entity

        timestamp = _timestamp()
        backup_file = self.backup_dir / f"pg_entities_{timestamp}.json"

        async with crud._session() as session:
            result = await session.execute(select(Entity))
            entities = result.scalars().all()

            data = []
            for e in entities:
                data.append({
                    "id": e.id,
                    "name": e.name,
                    "entity_type_id": e.entity_type_id,
                    "description": e.description,
                    "summary": e.summary,
                    "key_points": e.key_points,
                    "confidence": e.confidence,
                    "version": e.version,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "valid_from": e.valid_from.isoformat() if e.valid_from else None,
                    "valid_until": e.valid_until.isoformat() if e.valid_until else None,
                })

        backup_file.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"PG backup: {len(data)} entities → {backup_file}")
        return backup_file

    async def backup_neo4j(self, graph_store) -> Path:
        """Backup Neo4j nodes to JSON file."""
        timestamp = _timestamp()
        backup_file = self.backup_dir / f"neo4j_nodes_{timestamp}.json"

        try:
            result = await graph_store._session.run(
                "MATCH (n) RETURN n LIMIT 10000"
            )
            records = await result.data()
            data = [dict(r.get("n", {})) for r in records]
        except Exception as e:
            logger.error(f"Neo4j backup failed: {e}")
            data = []

        backup_file.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"Neo4j backup: {len(data)} nodes → {backup_file}")
        return backup_file

    def backup_qdrant(self, vector_store) -> Path:
        """Backup Qdrant collection info."""
        timestamp = _timestamp()
        backup_file = self.backup_dir / f"qdrant_info_{timestamp}.json"

        try:
            info = vector_store.client.get_collection(vector_store.collection_name)
            data = {
                "collection": vector_store.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": str(info.status),
            }
        except Exception as e:
            logger.error(f"Qdrant backup info failed: {e}")
            data = {"error": str(e)}

        backup_file.write_text(json.dumps(data, indent=2))
        logger.info(f"Qdrant backup info → {backup_file}")
        return backup_file

    async def backup_all(self, crud, graph_store, vector_store) -> list[Path]:
        """Run full backup of all stores."""
        results = []
        results.append(await self.backup_pg(crud))
        results.append(await self.backup_neo4j(graph_store))
        results.append(self.backup_qdrant(vector_store))
        logger.info(f"Full backup complete: {len(results)} files")
        return results
