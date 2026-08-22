"""Tests for parallel pipeline (TODO #31)."""
import asyncio
from src.pipeline.parallel import ParallelPipeline, PipelineStats


class TestParallelPipeline:
    """TODO #31: Pipeline parallelization."""

    def test_empty_batch(self):
        async def run():
            p = ParallelPipeline(max_concurrency=3)
            stats = await p.process_batch([], lambda x: asyncio.sleep(0))
            return stats
        stats = asyncio.run(run())
        assert stats.total == 0
        assert stats.success_rate == 0.0

    def test_successful_batch(self):
        async def run():
            p = ParallelPipeline(max_concurrency=3)
            results = []
            async def processor(x):
                results.append(x)
            stats = await p.process_batch([1, 2, 3], processor)
            return stats, results
        stats, results = asyncio.run(run())
        assert stats.completed == 3
        assert stats.failed == 0
        assert sorted(results) == [1, 2, 3]

    def test_concurrency_limit(self):
        async def run():
            p = ParallelPipeline(max_concurrency=2)
            max_concurrent = 0
            current = 0
            async def processor(x):
                nonlocal max_concurrent, current
                current += 1
                max_concurrent = max(max_concurrent, current)
                await asyncio.sleep(0.05)
                current -= 1
            stats = await p.process_batch(list(range(6)), processor)
            return stats, max_concurrent
        stats, max_concurrent = asyncio.run(run())
        assert stats.completed == 6
        assert max_concurrent <= 2

    def test_failure_handling(self):
        async def run():
            p = ParallelPipeline(max_concurrency=3)
            async def processor(x):
                if x == 2:
                    raise ValueError("bad item")
            stats = await p.process_batch([1, 2, 3], processor)
            return stats
        stats = asyncio.run(run())
        assert stats.completed == 2
        assert stats.failed == 1
        assert len(stats.errors) == 1
