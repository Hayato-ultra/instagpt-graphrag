"""Tests for pipeline-level entity deduplication (mirrors EntityResolver naming)."""

import pytest


@pytest.fixture
def enriched_entity():
    from src.config.models import EnrichedEntity

    def factory(name: str, confidence: float = 0.8):
        return EnrichedEntity(
            name=name,
            description=f"about {name}",
            source_chunk_id="chunk-1",
            source_url="https://example.com/reel",
            confidence=confidence,
        )

    return factory


def test_deduplicate_collapses_casing_and_spacing(enriched_entity):
    from src.pipeline.pipeline import deduplicate_entities

    entities = deduplicate_entities([
        enriched_entity("VS Code", 0.9),
        enriched_entity("vscode", 0.7),
    ])

    assert len(entities) == 1
    assert entities[0].name == "VS Code"


def test_deduplicate_keeps_highest_confidence(enriched_entity):
    from src.pipeline.pipeline import deduplicate_entities

    entities = deduplicate_entities([
        enriched_entity("PostgreSQL", 0.6),
        enriched_entity("PostgreSQL", 0.95),
    ])

    assert len(entities) == 1
    assert entities[0].confidence == 0.95


def test_deduplicate_preserves_distinct_normalized_names(enriched_entity):
    from src.pipeline.pipeline import deduplicate_entities

    entities = deduplicate_entities([
        enriched_entity("Docker"),
        enriched_entity("Kubernetes"),
    ])

    assert len(entities) == 2