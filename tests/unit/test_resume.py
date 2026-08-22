"""Tests for pipeline resume after crash — checkpoint data is preserved."""
from typing import Any

import pytest

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


class TestResume:
    @pytest.mark.asyncio
    async def test_checkpoint_data_preserved_on_resume(self):
        async def _extract(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"raw_text": "hello"}

        async def _chunk(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"chunks": ["c1", "c2"]}

        stages = [
            Stage(name="extract", order=1, fn=_extract),
            Stage(name="chunk", order=2, fn=_chunk),
        ]
        recorder = MemoryRecorder()
        await run_stages(stages, recorder)

        # Simulate crash: mark chunk as pending again
        recorder.steps["chunk"] = "pending"
        del recorder.checkpoints["chunk"]

        result = await run_stages(stages, recorder)
        assert result.success is True
        assert result.context["raw_text"] == "hello"
        assert result.context["chunks"] == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_crash_between_stages_preserves_earlier_checkpoints(self):
        call_count = {"enrich": 0}

        async def _fail_enrich(ctx: dict[str, Any]) -> dict[str, Any]:
            call_count["enrich"] += 1
            if call_count["enrich"] <= 1:
                raise RuntimeError("enrich crashed")
            return {"entities": []}

        async def _extract(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"raw": "text"}

        async def _chunk(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"chunks": []}

        stages = [
            Stage(name="extract", order=1, fn=_extract),
            Stage(name="chunk", order=2, fn=_chunk),
            Stage(name="enrich", order=3, fn=_fail_enrich),
        ]
        recorder = MemoryRecorder()
        result1 = await run_stages(stages, recorder)
        assert result1.success is False
        assert result1.failed_stage == "enrich"
        assert result1.context["raw"] == "text"

        result2 = await run_stages(stages, recorder)
        assert result2.success is True
        assert result2.context["raw"] == "text"
        assert result2.context["entities"] == []

    @pytest.mark.asyncio
    async def test_retry_after_failure_increases_attempt(self):
        attempt = {"count": 0}

        async def _flaky(ctx: dict[str, Any]) -> dict[str, Any]:
            attempt["count"] += 1
            if attempt["count"] == 1:
                raise RuntimeError("first attempt fails")
            return {"ok": True}

        stages = [Stage(name="flaky", order=1, fn=_flaky)]
        recorder = MemoryRecorder()

        result1 = await run_stages(stages, recorder)
        assert result1.success is False

        result2 = await run_stages(stages, recorder)
        assert result2.success is True

    @pytest.mark.asyncio
    async def test_heartbeat_called_during_resume(self):
        async def _a(ctx: dict[str, Any]) -> dict[str, Any]:
            return {}

        async def _b(ctx: dict[str, Any]) -> dict[str, Any]:
            return {}

        stages = [
            Stage(name="a", order=1, fn=_a),
            Stage(name="b", order=2, fn=_b),
        ]
        recorder = MemoryRecorder()
        recorder.steps["a"] = "completed"
        recorder.checkpoints["a"] = {}

        await run_stages(stages, recorder)
        assert recorder.heartbeat_count >= 1
