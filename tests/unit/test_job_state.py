"""Tests for PipelineJob state transitions via MemoryRecorder and run_stages."""
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


def _make_stage(name: str, order: int, output: dict = None, fail: bool = False):
    """Create a Stage that either succeeds or raises."""
    async def _fn(ctx: dict[str, Any]):
        if fail:
            raise RuntimeError(f"{name} failed intentionally")
        return output or {}
    return Stage(name=name, order=order, fn=_fn)


class TestRunStages:
    @pytest.mark.asyncio
    async def test_all_stages_run_in_order(self):
        recorder = MemoryRecorder()
        stages = [
            _make_stage("a", 1),
            _make_stage("b", 2),
            _make_stage("c", 3),
        ]
        result = await run_stages(stages, recorder)
        assert result.success is True
        assert result.completed_stages == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_stops_on_failure(self):
        recorder = MemoryRecorder()
        stages = [
            _make_stage("a", 1),
            _make_stage("b", 2, fail=True),
            _make_stage("c", 3),
        ]
        result = await run_stages(stages, recorder)
        assert result.success is False
        assert result.failed_stage == "b"
        assert result.completed_stages == ["a"]
        assert "c" not in recorder.steps  # never touched

    @pytest.mark.asyncio
    async def test_skips_completed_stages(self):
        recorder = MemoryRecorder()
        recorder.steps["a"] = "completed"
        recorder.checkpoints["a"] = {"value": 42}

        stages = [
            _make_stage("a", 1, output={"value": 42}),
            _make_stage("b", 2, output={"value": 99}),
        ]
        result = await run_stages(stages, recorder)
        assert result.success is True
        assert result.completed_stages == ["a", "b"]
        assert result.context["value"] == 99

    @pytest.mark.asyncio
    async def test_context_propagation(self):
        recorder = MemoryRecorder()
        stages = [
            _make_stage("extract", 1, output={"raw": "hello"}),
            _make_stage("process", 2, output={"processed": "HELLO"}),
        ]
        result = await run_stages(stages, recorder, initial_context={"url": "test"})
        assert result.context["url"] == "test"
        assert result.context["raw"] == "hello"
        assert result.context["processed"] == "HELLO"

    @pytest.mark.asyncio
    async def test_empty_stages_list(self):
        recorder = MemoryRecorder()
        result = await run_stages([], recorder)
        assert result.success is True
        assert result.completed_stages == []

    @pytest.mark.asyncio
    async def test_stages_run_in_order_even_if_out_of_order(self):
        recorder = MemoryRecorder()
        stages = [
            _make_stage("c", 3),
            _make_stage("a", 1),
            _make_stage("b", 2),
        ]
        result = await run_stages(stages, recorder)
        assert result.success is True
        assert result.completed_stages == ["a", "b", "c"]


class TestMemoryRecorder:
    @pytest.mark.asyncio
    async def test_begin_step_sets_running(self):
        rec = MemoryRecorder()
        await rec.begin_step("extract")
        assert rec.steps["extract"] == "running"

    @pytest.mark.asyncio
    async def test_complete_step_sets_completed(self):
        rec = MemoryRecorder()
        await rec.complete_step("extract", {"key": "val"})
        assert rec.steps["extract"] == "completed"
        assert rec.checkpoints["extract"] == {"key": "val"}

    @pytest.mark.asyncio
    async def test_fail_step_sets_failed(self):
        rec = MemoryRecorder()
        await rec.fail_step("extract", "boom")
        assert rec.steps["extract"] == "failed"
        assert rec.errors["extract"] == "boom"

    @pytest.mark.asyncio
    async def test_is_step_completed(self):
        rec = MemoryRecorder()
        assert await rec.is_step_completed("x") is False
        await rec.complete_step("x", {})
        assert await rec.is_step_completed("x") is True

    @pytest.mark.asyncio
    async def test_heartbeat_increments(self):
        rec = MemoryRecorder()
        await rec.heartbeat()
        assert rec.heartbeat_count == 1
