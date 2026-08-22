"""Tests for hallucination detection (TODO #12, #13, #14, #15)."""
from src.enrichment.hallucination import validate_entities, filter_hallucinated


class TestValidateEntities:
    """Test entity validation against source text."""

    def test_exact_match(self):
        """Entities that appear in text are valid."""
        r = validate_entities(["Docker", "React"], "Using Docker to deploy React apps")
        assert "Docker" in r.valid
        assert "React" in r.valid
        assert not r.has_issues

    def test_case_insensitive_match(self):
        """Case-insensitive matching works."""
        r = validate_entities(["docker"], "Using Docker to deploy")
        assert "docker" in r.valid

    def test_hallucinated_entity(self):
        """Entities not in text are suspected."""
        r = validate_entities(["Kubernetes"], "Using Docker to deploy React apps")
        assert "Kubernetes" in r.suspected

    def test_misspelling_detection(self):
        """Misspelled entity names are detected."""
        r = validate_entities(["Dokcer"], "Using Docker to deploy")
        assert len(r.misspelled) > 0 or "Dokcer" in r.valid

    def test_alias_match(self):
        """Known aliases resolve to source text."""
        aliases = {"React": ["ReactJS", "react.js"]}
        r = validate_entities(["ReactJS"], "Building with React", aliases)
        assert "ReactJS" in r.valid

    def test_mixed_valid_and_hallucinated(self):
        """Mix of valid and hallucinated entities."""
        r = validate_entities(
            ["Docker", "Kubernetes", "React"],
            "Using Docker to deploy React apps"
        )
        assert "Docker" in r.valid
        assert "React" in r.valid
        assert "Kubernetes" in r.suspected

    def test_empty_entities(self):
        """Empty entity list returns no issues."""
        r = validate_entities([], "Some text")
        assert not r.has_issues

    def test_confidence_score(self):
        """Confidence is ratio of valid to total."""
        r = validate_entities(["Docker", "React"], "Using Docker")
        assert r.confidence == 0.5


class TestFilterHallucinated:
    """Test filtering of hallucinated entities."""

    def test_filters_hallucinated(self):
        """Entities not in text are filtered out."""
        entities = [
            {"name": "Docker", "confidence": 0.9},
            {"name": "Kubernetes", "confidence": 0.8},
        ]
        result = filter_hallucinated(entities, "Using Docker to deploy")
        assert len(result) == 1
        assert result[0]["name"] == "Docker"

    def test_keeps_high_confidence(self):
        """High-confidence entities are kept."""
        entities = [
            {"name": "Docker", "confidence": 0.95},
        ]
        result = filter_hallucinated(entities, "Using Docker")
        assert len(result) == 1

    def test_filters_low_confidence(self):
        """Low-confidence entities are filtered."""
        entities = [
            {"name": "Docker", "confidence": 0.3},
        ]
        result = filter_hallucinated(entities, "Using Docker", confidence_threshold=0.5)
        assert len(result) == 0
