"""Resumable pipeline coordinator.

Run ordered stages through a BaseRecorder. Already-completed stages
are skipped on resume. Each stage receives a context dict carrying
data from prior stages.
"""
from __future__ import annotations

import traceback
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.pipeline.recorder import BaseRecorder


@dataclass
class Stage:
    """One pipeline stage to be executed."""
    name: str
    order: int
    # Async callable that receives (context) and returns checkpoint updates
    fn: Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]
    # If True, failure of this stage should mark the whole job as dead-letter
    critical: bool = True


@dataclass
class StageResult:
    """Result after running all stages."""
    success: bool
    completed_stages: list[str] = field(default_factory=list)
    failed_stage: str | None = None
    error: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


async def run_stages(
    stages: list[Stage],
    recorder: BaseRecorder,
    initial_context: dict[str, Any] | None = None,
) -> StageResult:
    """Execute stages in order, skipping completed ones.

    Each stage's output dict is merged into the context, so later stages
    can access data produced by earlier ones.

    Args:
        stages: Ordered list of Stage objects.
        recorder: Checkpoint recorder (SQLPipelineRecorder or NullRecorder).
        initial_context: Pre-populated context (e.g. url, job_id).

    Returns:
        StageResult with success/failure and final context.
    """
    context: dict[str, Any] = dict(initial_context or {})
    completed: list[str] = []
    failed_stage: str | None = None
    error_msg: str | None = None

    for stage in sorted(stages, key=lambda s: s.order):
        await recorder.heartbeat()

        if await recorder.is_step_completed(stage.name):
            checkpoint = await recorder.get_checkpoint(stage.name)
            context.update(checkpoint)
            completed.append(stage.name)
            logger.info(f"Stage '{stage.name}' already completed, skipping")
            continue

        try:
            await recorder.begin_step(stage.name)
            updates = await stage.fn(context)
            context.update(updates)
            await recorder.complete_step(stage.name, updates)
            completed.append(stage.name)
            logger.info(f"Stage '{stage.name}' completed successfully")
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Stage '{stage.name}' failed: {e}\n{tb}")
            await recorder.fail_step(stage.name, str(e))
            failed_stage = stage.name
            error_msg = str(e)
            break

    success = failed_stage is None
    return StageResult(
        success=success,
        completed_stages=completed,
        failed_stage=failed_stage,
        error=error_msg,
        context=context,
    )
