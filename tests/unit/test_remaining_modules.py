"""Tests for video optimizer, URL enrichment, output format, lifecycle, and versions."""
import asyncio
from src.extraction.video_optimizer import (
    calculate_optimal_interval,
    select_key_frames,
    FrameSamplingConfig,
)
from src.enrichment.output_format import format_output, _is_project_entity
from src.pipeline.versions import get_current_versions, set_versions, PipelineVersions


class TestVideoOptimizer:
    """TODO #42: Video processing optimization."""

    def test_optimal_interval_short_video(self):
        assert calculate_optimal_interval(30, 10) == 3.0

    def test_optimal_interval_long_video(self):
        assert calculate_optimal_interval(600, 10) == 10.0  # Capped at 10s

    def test_optimal_interval_very_short(self):
        assert calculate_optimal_interval(5, 10) == 0.5  # Min 0.5s

    def test_select_key_frames_empty(self):
        assert select_key_frames([]) == []

    def test_select_key_frames_with_content(self):
        # Frames with some non-zero bytes
        frames = [bytes([1] * 1000) for _ in range(10)]
        selected = select_key_frames(frames)
        assert len(selected) > 0
        assert len(selected) <= 15

    def test_select_key_frames_max_limit(self):
        frames = [bytes([i] * 1000) for i in range(50)]
        selected = select_key_frames(frames, FrameSamplingConfig(max_frames=5))
        assert len(selected) <= 5


class TestPipelineVersions:
    """TODO #60: Pipeline version tracking."""

    def test_get_versions(self):
        v = get_current_versions()
        assert isinstance(v, PipelineVersions)
        assert v.pipeline_version == "1.0.0"

    def test_set_versions(self):
        v = set_versions(model_version="gpt-4o-mini", prompt_version="v2")
        assert v.model_version == "gpt-4o-mini"
        assert v.prompt_version == "v2"

    def test_to_dict(self):
        v = get_current_versions()
        d = v.to_dict()
        assert "pipeline_version" in d
        assert "model_version" in d


class TestOutputFormatExtended:
    """Additional output format tests."""

    def test_project_detection_web_app(self):
        assert _is_project_entity({"name": "TodoApp", "type": "web_app"})

    def test_project_detection_description(self):
        assert _is_project_entity({"name": "X", "description": "Build a REST API"})

    def test_format_separates_projects(self):
        entities = [
            {"name": "Docker", "type": "tool"},
            {"name": "MyApp", "type": "web_app"},
        ]
        output = format_output(entities)
        assert len(output.entities) == 1
        assert len(output.projects) == 1
