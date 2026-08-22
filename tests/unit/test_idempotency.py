"""Tests for content-hash idempotency across the pipeline."""
from typing import Any

import pytest

from src.pipeline.pipeline import content_hash
from src.pipeline.recorder import BaseRecorder
from src.pipeline.resumable import Stage, run_stages


class MemoryRecorder(BaseRecorder):
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


class TestContentHashIdempotency:
    def test_same_url_same_hash(self):
        h1 = content_hash("https://example.com/post?utm_source=twitter&id=42")
        h2 = content_hash("https://example.com/post?utm_source=facebook&id=42")
        assert h1 == h2

    def test_different_urls_different_hash(self):
        h1 = content_hash("https://example.com/post-a")
        h2 = content_hash("https://example.com/post-b")
        assert h1 != h2

    @pytest.mark.asyncio
    async def test_resume_skips_completed_stages(self):
        call_log = []

        async def _track(ctx: dict[str, Any]) -> dict[str, Any]:
            call_log.append("extract")
            return {"raw": "data"}

        async def _track2(ctx: dict[str, Any]) -> dict[str, Any]:
            call_log.append("chunk")
            return {"chunks": []}

        stages = [
            Stage(name="extract", order=1, fn=_track),
            Stage(name="chunk", order=2, fn=_track2),
        ]

        recorder = MemoryRecorder()
        result1 = await run_stages(stages, recorder)
        assert result1.success is True
        assert call_log == ["extract", "chunk"]

        # Simulate crash: reset chunk to pending
        recorder.steps["chunk"] = "pending"
        del recorder.checkpoints["chunk"]
        call_log.clear()

        # Resume — only chunk re-runs
        result2 = await run_stages(stages, recorder)
        assert result2.success is True
        assert call_log == ["chunk"]

    @pytest.mark.asyncio
    async def test_idempotent_submissions(self):
        recorder = MemoryRecorder()

        async def _extract(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True}

        stages = [Stage(name="extract", order=1, fn=_extract)]

        h = content_hash("https://example.com/post")

        result1 = await run_stages(stages, recorder)
        assert result1.success is True

        assert await recorder.is_step_completed("extract") is True
