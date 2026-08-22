"""Tests for retrieval quality and context window (TODO #55, #56)."""
from src.search.retrieval import (
    filter_and_rank_results,
    fit_context_window,
    _entity_type_diversity,
    RetrievalConfig,
)


class TestRetrievalQuality:
    """TODO #55: Retrieval quality filtering."""

    def test_filters_low_score(self):
        results = [
            {"name": "A", "score": 0.8, "entity_type": "tool"},
            {"name": "B", "score": 0.1, "entity_type": "tool"},
        ]
        filtered = filter_and_rank_results(results, RetrievalConfig(min_relevance_score=0.3))
        assert len(filtered) == 1
        assert filtered[0]["name"] == "A"

    def test_diversity_boost(self):
        results = [
            {"name": "A", "score": 0.5, "entity_type": "tool"},
            {"name": "B", "score": 0.5, "entity_type": "framework"},
            {"name": "C", "score": 0.5, "entity_type": "tool"},
        ]
        filtered = filter_and_rank_results(results, RetrievalConfig(diversity_weight=0.2))
        # B should be boosted (only one of its type)
        assert filtered[0]["name"] == "B"

    def test_limits_results(self):
        results = [{"name": f"R{i}", "score": 0.9, "entity_type": "tool"} for i in range(30)]
        filtered = filter_and_rank_results(results, RetrievalConfig(max_results=5))
        assert len(filtered) == 5


class TestContextWindow:
    """TODO #56: Context window fitting."""

    def test_fits_all_if_enough_budget(self):
        results = [
            {"name": "Docker", "description": "Container tool"},
            {"name": "React", "description": "UI library"},
        ]
        fitted = fit_context_window(results, max_tokens=10000)
        assert len(fitted) == 2

    def test_truncates_to_budget(self):
        results = [
            {"name": "Docker", "description": "A" * 1000},
            {"name": "React", "description": "B" * 1000},
            {"name": "Vue", "description": "C" * 1000},
        ]
        fitted = fit_context_window(results, max_tokens=200)
        assert len(fitted) < 3

    def test_empty_results(self):
        assert fit_context_window([], max_tokens=100) == []


class TestDiversity:
    """Entity type diversity calculation."""

    def test_high_diversity(self):
        results = [
            {"entity_type": "tool"},
            {"entity_type": "framework"},
            {"entity_type": "library"},
            {"entity_type": "concept"},
            {"entity_type": "platform"},
        ]
        assert _entity_type_diversity(results) == 1.0

    def test_low_diversity(self):
        results = [{"entity_type": "tool"} for _ in range(5)]
        assert _entity_type_diversity(results) == 0.2
