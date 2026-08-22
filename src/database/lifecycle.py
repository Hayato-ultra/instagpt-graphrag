"""Data lifecycle and storage growth management (TODO #63).

Provides retention policies and cleanup for old data.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loguru import logger


class LifecycleManager:
    """Manage data lifecycle and retention (TODO #63)."""

    def __init__(
        self,
        entity_retention_days: int = 365,
        episodic_retention_days: int = 90,
        outbox_retention_days: int = 30,
    ) -> None:
        self.entity_retention_days = entity_retention_days
        self.episodic_retention_days = episodic_retention_days
        self.outbox_retention_days = outbox_retention_days

    async def cleanup_expired_entities(self, crud) -> int:
        """Remove entities past their valid_until date."""
        from sqlalchemy import select

        from src.database.models import Entity

        cutoff = datetime.now(UTC).replace(tzinfo=None)
        count = 0

        async with crud._session() as session:
            result = await session.execute(
                select(Entity).where(
                    Entity.valid_until.isnot(None),
                    Entity.valid_until < cutoff,
                )
            )
            expired = result.scalars().all()

            for entity in expired:
                await session.delete(entity)
                count += 1

            await session.commit()

        if count > 0:
            logger.info(f"Lifecycle: removed {count} expired entities")
        return count

    async def cleanup_old_episodic_memories(self, crud) -> int:
        """Remove episodic memories older than retention period."""
        from sqlalchemy import select

        from src.database.models import EpisodicMemory

        cutoff = (datetime.now(UTC) - timedelta(days=self.episodic_retention_days)).replace(tzinfo=None)
        count = 0

        async with crud._session() as session:
            result = await session.execute(
                select(EpisodicMemory).where(EpisodicMemory.created_at < cutoff)
            )
            old_memories = result.scalars().all()

            for memory in old_memories:
                await session.delete(memory)
                count += 1

            await session.commit()

        if count > 0:
            logger.info(f"Lifecycle: removed {count} old episodic memories")
        return count

    async def cleanup_old_outbox_events(self, crud) -> int:
        """Remove completed/failed outbox events older than retention."""
        from sqlalchemy import select

        from src.database.models import OutboxEvent

        cutoff = (datetime.now(UTC) - timedelta(days=self.outbox_retention_days)).replace(tzinfo=None)
        count = 0

        async with crud._session() as session:
            result = await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.status.in_(["completed", "failed"]),
                    OutboxEvent.created_at < cutoff,
                )
            )
            old_events = result.scalars().all()

            for event in old_events:
                await session.delete(event)
                count += 1

            await session.commit()

        if count > 0:
            logger.info(f"Lifecycle: removed {count} old outbox events")
        return count

    async def run_full_cleanup(self, crud) -> dict[str, int]:
        """Run all lifecycle cleanup tasks."""
        results = {
            "expired_entities": await self.cleanup_expired_entities(crud),
            "old_episodic_memories": await self.cleanup_old_episodic_memories(crud),
            "old_outbox_events": await self.cleanup_old_outbox_events(crud),
        }
        total = sum(results.values())
        if total > 0:
            logger.info(f"Lifecycle cleanup: {results}")
        return results
