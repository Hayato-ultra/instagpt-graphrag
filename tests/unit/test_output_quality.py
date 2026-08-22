"""Tests for output quality validators (TODO #19, #23, #30)."""
from src.enrichment.enrichment import (
    is_garbled_text,
    has_duplicate_content,
    validate_key_points,
)


class TestGarbledText:
    """TODO #19: Detect garbled/truncated summary text."""

    def test_clean_text_passes(self):
        assert not is_garbled_text("This is a clear summary of the content.")

    def test_empty_text_fails(self):
        assert is_garbled_text("")

    def test_short_text_fails(self):
        assert is_garbled_text("Hi")

    def test_repeated_chars_detected(self):
        assert is_garbled_text("This has aaaaa repeated characters")

    def test_multiple_question_marks_detected(self):
        assert is_garbled_text("What is this???")

    def test_normal_unicode_passes(self):
        assert not is_garbled_text("Using café and naïve in sentences")


class TestDuplicateContent:
    """TODO #23: Detect key points duplicating summary."""

    def test_no_duplicate(self):
        summary = "Docker is a containerization platform."
        key_points = ["Install Docker Desktop", "Create a Dockerfile", "Build the image"]
        assert not has_duplicate_content(summary, key_points)

    def test_duplicate_detected(self):
        summary = "Docker is a containerization platform for deploying apps."
        key_points = ["Docker is a containerization platform for deploying apps."]
        assert has_duplicate_content(summary, key_points)

    def test_empty_inputs(self):
        assert not has_duplicate_content("", [])
        assert not has_duplicate_content("Summary", [])


class TestKeyPointsValidation:
    """TODO #30: Validate extracted key points."""

    def test_filters_empty_points(self):
        result = validate_key_points(["", "  ", "Valid point here"])
        assert len(result) == 1

    def test_removes_duplicates(self):
        result = validate_key_points(["First point with enough text", "first point with enough text", "Second point with enough text"])
        assert len(result) == 2

    def test_limits_to_max(self):
        points = [f"Point {i} with enough text to pass validation" for i in range(10)]
        result = validate_key_points(points, max_points=5)
        assert len(result) == 5

    def test_empty_input(self):
        assert validate_key_points([]) == []
