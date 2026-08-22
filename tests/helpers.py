"""Shared test helpers — importable from any test file."""
from __future__ import annotations

from typing import Any

from src.pipeline.recorder import BaseRecorder


class MemoryRecorder(BaseRecorder):
    """In-memory recorder for unit tests. Tracks steps without any DB."""

    def __init__(self):
        self.steps: dict[str, str] = {}
        self.checkpoints: dict[str, dict[str, Any]] = {}
        self.errors: dict[str, str] = {}
        self.heartbeat_count = 0

    async def begin_step(self, step_name: str) -> None:
        self.steps[step_name] = "running"

    async def complete_step(self, step_name: str, checkpoint_data: dict[str, Any]) -> None:
        self.steps[step_name] = "completed"
        self.checkpoints[step_name] = checkpoint_data

    async def fail_step(self, step_name: str, error: str) -> None:
        self.steps[step_name] = "failed"
        self.errors[step_name] = error

    async def is_step_completed(self, step_name: str) -> bool:
        return self.steps.get(step_name) == "completed"

    async def get_checkpoint(self, step_name: str) -> dict[str, Any]:
        return self.checkpoints.get(step_name, {})

    async def heartbeat(self) -> None:
        self.heartbeat_count += 1
