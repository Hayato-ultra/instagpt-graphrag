"""Pipeline job recorder: bridges pipeline stages to database checkpoints.

SQLPipelineRecorder writes per-step checkpoints to PostgreSQL via CRUDOperations.
NullRecorder is the no-op default used when no DB session is available.
"""
from __future__ import annotations

import abc
from datetime import datetime
from typing import Any

from loguru import logger

from src.database.models import StepStatus


class BaseRecorder(abc.ABC):
    """Abstract recorder for pipeline step checkpoints."""

    @abc.abstractmethod
    async def begin_step(self, step_name: str) -> None:
        """Mark a step as RUNNING."""

    @abc.abstractmethod
    async def complete_step(self, step_name: str, checkpoint_data: dict[str, Any]) -> None:
        """Mark a step as COMPLETED with checkpoint data."""

    @abc.abstractmethod
    async def fail_step(self, step_name: str, error: str) -> None:
        """Mark a step as FAILED with error message."""

    @abc.abstractmethod
    async def is_step_completed(self, step_name: str) -> bool:
        """Check if a step was already completed (for resume)."""

    @abc.abstractmethod
    async def get_checkpoint(self, step_name: str) -> dict[str, Any]:
        """Retrieve checkpoint data for a completed step."""

    @abc.abstractmethod
    async def heartbeat(self) -> None:
        """Refresh heartbeat to prevent stale-job detection."""


class NullRecorder(BaseRecorder):
    """No-op recorder for testing or standalone pipeline runs."""

    async def begin_step(self, step_name: str) -> None:
        pass

    async def complete_step(self, step_name: str, checkpoint_data: dict[str, Any]) -> None:
        pass

    async def fail_step(self, step_name: str, error: str) -> None:
        pass

    async def is_step_completed(self, step_name: str) -> bool:
        return False

    async def get_checkpoint(self, step_name: str) -> dict[str, Any]:
        return {}

    async def heartbeat(self) -> None:
        pass


class SQLPipelineRecorder(BaseRecorder):
    """Records pipeline step checkpoints to PostgreSQL via CRUDOperations.

    Each stage (extract, chunk, embed, enrich, categorize, format, graph_update)
    writes a checkpoint on completion. On resume, completed steps are skipped.
    """

    HEARTBEAT_INTERVAL_SECONDS = 120

    def __init__(self, crud: CRUDOperations, job_id: str):
        self._crud = crud
        self._job_id = job_id
        self._last_heartbeat: datetime | None = None

    async def begin_step(self, step_name: str) -> None:
        await self._crud.upsert_pipeline_step(
            self._job_id, step_name, StepStatus.RUNNING
        )
        logger.debug(f"Step {step_name} → RUNNING (job={self._job_id})")

    async def complete_step(self, step_name: str, checkpoint_data: dict[str, Any]) -> None:
        await self._crud.upsert_pipeline_step(
            self._job_id, step_name, StepStatus.COMPLETED, checkpoint_data=checkpoint_data
        )
        logger.debug(f"Step {step_name} → COMPLETED (job={self._job_id})")

    async def fail_step(self, step_name: str, error: str) -> None:
        await self._crud.upsert_pipeline_step(
            self._job_id, step_name, StepStatus.FAILED, error=error
        )
        logger.warning(f"Step {step_name} → FAILED: {error} (job={self._job_id})")

    async def is_step_completed(self, step_name: str) -> bool:
        steps = await self._crud.get_pipeline_steps(self._job_id)
        for s in steps:
            if s.step_name == step_name and s.status == StepStatus.COMPLETED:
                return True
        return False

    async def get_checkpoint(self, step_name: str) -> dict[str, Any]:
        steps = await self._crud.get_pipeline_steps(self._job_id)
        for s in steps:
            if s.step_name == step_name and s.status == StepStatus.COMPLETED:
                return s.checkpoint_data or {}
        return {}

    async def heartbeat(self) -> None:
        now = datetime.utcnow()
        if (
            self._last_heartbeat is None
            or (now - self._last_heartbeat).total_seconds() > self.HEARTBEAT_INTERVAL_SECONDS
        ):
            await self._crud.update_job_heartbeat(self._job_id)
            self._last_heartbeat = now
