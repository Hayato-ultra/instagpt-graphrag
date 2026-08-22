"""Unit tests for the entity-resolution benchmark harness.

Covers:
- Golden dataset loading/validation.
- Decision mapping from ResolutionResult.
- Deterministic Precision/Recall/F1 scoring via a stub resolver.
- End-to-end synthetic run against the golden fixture.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.graph.entity_resolver import Resolution, ResolutionResult
from src.graph.resolution_benchmark import (
    GOLDEN_FIXTURE,
    BenchmarkResult,
    build_synthetic_resolver,
    decision_from_resolution,
    load_dataset,
    run_benchmark,
    run_synthetic_benchmark,
    score,
)


class StubResolver:
    """Resolver that returns a canned decision per pair id."""

    def __init__(self, decisions: dict[str, ResolutionResult]):
        self._decisions = decisions

    async def resolve(self, name, entity_type, description, graph_store=None):
        return self._decisions.get(name, {})["result"]


# ─── Dataset loading ─────────────────────────────────────────────────────────


def test_golden_fixture_exists_and_is_valid():
    assert GOLDEN_FIXTURE.exists(), f"missing golden fixture: {GOLDEN_FIXTURE}"
    data = load_dataset(GOLDEN_FIXTURE)
    assert data["existing_entities"]
    assert data["pairs"]
    assert data["pairs"][0]["expected"]["decision"] in {"MERGE", "SIMILAR", "NEW"}


def test_load_dataset_rejects_unknown_canonical(tmp_path: Path):
    fixture = tmp_path / "bad.json"
    fixture.write_text(
        '{"existing_entities": [{"id": "e-1", "name": "X", "type": "t"}], '
        '"pairs": [{"id": "p-1", "category": "x", "query": {"name": "Y"}, '
        '"expected": {"decision": "MERGE", "canonical_id": "missing"}}]}',
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="unknown canonical"):
        load_dataset(fixture)


def test_load_dataset_rejects_new_with_canonical(tmp_path: Path):
    fixture = tmp_path / "bad.json"
    fixture.write_text(
        '{"existing_entities": [{"id": "e-1", "name": "X", "type": "t"}], '
        '"pairs": [{"id": "p-1", "category": "x", "query": {"name": "Y"}, '
        '"expected": {"decision": "NEW", "canonical_id": "e-1"}}]}',
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        load_dataset(fixture)


# ─── Decision mapping ────────────────────────────────────────────────────────


def test_decision_from_resolution():
    assert (
        decision_from_resolution(ResolutionResult(decision=Resolution.MERGE))
        == "MERGE"
    )
    assert (
        decision_from_resolution(ResolutionResult(decision=Resolution.SIMILAR))
        == "SIMILAR"
    )
    assert decision_from_resolution(ResolutionResult(decision=Resolution.NEW)) == "NEW"


# ─── Scoring math ────────────────────────────────────────────────────────────


def _row(expected_decision, actual_decision, expected_canonical, actual_canonical, correct):
    return BenchmarkResult(
        pair_id="p",
        category="cat",
        expected_decision=expected_decision,
        actual_decision=actual_decision,
        expected_canonical=expected_canonical,
        actual_canonical=actual_canonical,
        correct=correct,
    )


def test_score_treats_new_as_negative_class():
    rows = [
        _row("NEW", "NEW", None, None, correct=True),
        _row("NEW", "NEW", None, None, correct=True),
        _row("MERGE", "MERGE", "e-1", "e-1", correct=True),
    ]
    metrics = score(rows)["overall"]
    # 2 NEWs are negatives; precision/recall only cover the MERGE positive.
    assert metrics["decision_accuracy"] == 1.0
    assert metrics["entity_accuracy"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_score_reports_failed_positives():
    rows = [
        _row("MERGE", "MERGE", "e-1", "e-1", correct=True),
        _row("MERGE", "MERGE", "e-2", "e-9", correct=False),  # wrong entity
        _row("MERGE", "NEW", "e-3", None, correct=False),  # missed, returned NEW
    ]
    metrics = score(rows)["overall"]
    assert metrics["decision_accuracy"] == round(2 / 3, 3)
    assert metrics["entity_accuracy"] == round(1 / 3, 3)
    # positives=3, found=1 (e-1), returned=2
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == round(1 / 3, 3)


def test_score_groups_by_category():
    rows = [
        BenchmarkResult("1", "a", "NEW", "NEW", None, None, True),
        BenchmarkResult("2", "b", "MERGE", "MERGE", "e", "e", True),
    ]
    metrics = score(rows)
    assert set(metrics["by_category"]) == {"a", "b"}
    assert metrics["by_category"]["a"]["decision_accuracy"] == 1.0


# ─── Stub-driven benchmark end-to-end ────────────────────────────────────────


async def test_run_benchmark_with_stub_resolver():
    dataset = load_dataset(GOLDEN_FIXTURE)
    perfect = {
        pair["query"]["name"]: {
            "result": ResolutionResult(
                decision=(
                    Resolution.NEW
                    if pair["expected"]["decision"] == "NEW"
                    else Resolution.MERGE
                ),
                existing_entity_id=pair["expected"].get("canonical_id"),
            )
        }
        for pair in dataset["pairs"]
    }
    results = await run_benchmark(StubResolver(perfect), dataset)
    assert len(results) == len(dataset["pairs"])
    assert all(r.correct for r in results)
    assert score(results)["overall"]["f1"] == 1.0


# ─── Synthetic benchmark (real resolver, fake stores) ────────────────────────


async def test_synthetic_benchmark_runs_and_reports():
    dataset = load_dataset(GOLDEN_FIXTURE)
    resolver, graph = build_synthetic_resolver(dataset)
    results = await run_benchmark(resolver, dataset, graph_store=graph)
    metrics = score(results)
    assert metrics["total_pairs"] == len(dataset["pairs"])
    for key in ("decision_accuracy", "entity_accuracy", "precision", "recall", "f1"):
        assert 0.0 <= metrics["overall"][key] <= 1.0
    assert isinstance(metrics["by_category"], dict)


async def test_run_synthetic_benchmark_entrypoint():
    metrics = await run_synthetic_benchmark()
    assert metrics["total_pairs"] >= 1
    assert metrics["overall"]["count"] == metrics["total_pairs"]


# ─── Deterministic embedder sanity ───────────────────────────────────────────


def test_deterministic_embedder_orders_similar_higher():
    from src.graph.resolution_benchmark import DeterministicEmbedder, _cosine

    embedder = DeterministicEmbedder()
    docker = embedder.embed("docker platform containerization")
    typo = embedder.embed("dockr platform containerization")
    unrelated = embedder.embed("react framework ui library")

    assert _cosine(typo, docker) > 0.7
    assert _cosine(unrelated, docker) < _cosine(typo, docker)


# ─── Normalized-name alias resolution ────────────────────────────────────────


def test_normalize_name():
    from src.graph.entity_resolver import normalize_name

    assert normalize_name("VS Code") == normalize_name("VSCode") == normalize_name("vs-code")
    assert normalize_name(" PostgreSQL ") == "postgresql"


async def test_synthetic_resolver_merges_spacing_alias():
    """'VSCode' must MERGE into 'VS Code' via normalized-name alias (res-03)."""
    from src.graph.entity_resolver import Resolution
    from src.graph.resolution_benchmark import build_synthetic_resolver, load_dataset

    dataset = load_dataset(GOLDEN_FIXTURE)
    resolver, graph = build_synthetic_resolver(dataset)

    result = await resolver.resolve(
        name="VSCode", entity_type="tool", description="Code editor", graph_store=graph
    )

    assert result.decision == Resolution.MERGE
    assert result.existing_entity_name == "VS Code"
    assert result.existing_entity_id == "ent-vscode"


async def test_synthetic_resolver_does_not_merge_unrelated():
    """A genuinely new entity must still resolve to NEW (res-08)."""
    from src.graph.entity_resolver import Resolution
    from src.graph.resolution_benchmark import build_synthetic_resolver, load_dataset

    dataset = load_dataset(GOLDEN_FIXTURE)
    resolver, graph = build_synthetic_resolver(dataset)

    result = await resolver.resolve(
        name="Kubernetes", entity_type="platform",
        description="Container orchestration", graph_store=graph,
    )

    assert result.decision == Resolution.NEW
    assert result.existing_entity_id is None
