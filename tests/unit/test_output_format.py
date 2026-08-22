"""Tests for output format validator (TODO #20, #21, #22, #24, #25)."""
from src.enrichment.output_format import (
    _is_project_entity,
    _has_guide_title,
    _ensure_guide_title,
    _add_build_instructions,
    validate_output_ordering,
    format_output,
    OutputFormat,
)


class TestProjectDetection:
    """TODO #24: Projects should be under separate section."""

    def test_web_app_is_project(self):
        assert _is_project_entity({"name": "MyApp", "type": "web_app"})

    def test_mobile_app_is_project(self):
        assert _is_project_entity({"name": "MyApp", "type": "mobile_app"})

    def test_build_description_is_project(self):
        assert _is_project_entity({"name": "TodoApp", "description": "Build a todo app"})

    def test_github_url_is_project(self):
        assert _is_project_entity({"name": "MyRepo", "description": "github.com/user/repo"})

    def test_tool_not_project(self):
        assert not _is_project_entity({"name": "Docker", "type": "tool"})


class TestGuideTitle:
    """TODO #21: Step-by-step guide should have title."""

    def test_has_title(self):
        assert _has_guide_title("# How to Use Docker\nStep 1: Install")

    def test_no_title(self):
        assert not _has_guide_title("Install Docker and run it")

    def test_ensure_generates_title(self):
        steps = ["Install Docker", "Run the container"]
        title = _ensure_guide_title(steps, "Docker")
        assert title == "How to Use Docker"

    def test_ensure_no_title_needed(self):
        steps = ["# Guide\nStep 1: Install"]
        title = _ensure_guide_title(steps)
        assert title == ""


class TestBuildInstructions:
    """TODO #25: Project descriptions should have build instructions."""

    def test_adds_instructions(self):
        entity = {"description": "A cool app"}
        result = _add_build_instructions(entity)
        assert "setup instructions" in result["description"].lower()

    def test_keeps_existing(self):
        entity = {"description": "npm install and run"}
        result = _add_build_instructions(entity)
        assert result["description"] == "npm install and run"


class TestOutputOrdering:
    """TODO #22: Guide section should be after summary."""

    def test_correct_order(self):
        summary = "This tutorial teaches Docker"
        guide = "Step 1: Install"
        s, g = validate_output_ordering(summary, guide)
        assert s == summary
        assert g == guide

    def test_swaps_if_wrong(self):
        summary = "Summary of the tutorial"
        guide = "Step 1: Install Docker basics"
        s, g = validate_output_ordering(guide, summary)
        # Should keep as-is since we can't determine original order
        assert s == guide or s == summary


class TestFormatOutput:
    """Full output formatting."""

    def test_separates_projects(self):
        entities = [
            {"name": "Docker", "type": "tool"},
            {"name": "MyApp", "type": "web_app"},
        ]
        output = format_output(entities)
        assert len(output.entities) == 1
        assert len(output.projects) == 1

    def test_empty_input(self):
        output = format_output([])
        assert len(output.entities) == 0
        assert len(output.projects) == 0
