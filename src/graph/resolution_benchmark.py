"""Entity-resolution benchmark: dataset + harness.

Phase 2, item 1 of docs/instagpt_graphrag_problems_solutions.txt.

The current resolver (EntityResolver) reduces to exact-name match plus an
embedding-similarity lookup. This benchmark quantifies that behavior against a
golden dataset so resolver improvements (alias matching, normalization, graph
similarity, LLM verification) can be tracked with precision/recall/F1 instead
of anecdotes.

Two modes:
- Synthetic: run the real EntityResolver against deterministic fake stores
  (no external services). Used by the CLI and CI.
- Stub: the scoring math is unit-tested with a stub resolver.

Metrics produced per category and overall:
- decision_accuracy: fraction where the returned decision matches the golden one.
- entity_accuracy: fraction where the returned existing entity (or NEW) matches
  the golden canonical entity.
- precision / recall / F1 treating "resolved to the golden canonical entity" as
  the positive class.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.graph.entity_resolver import Resolution, ResolutionResult

_GOLDEN_REL = Path("tests") / "fixtures" / "golden" / "resolution" / "entity_resolution.json"
GOLDEN_FIXTURE = Path(__file__).resolve().parents[2] / _GOLDEN_REL


@dataclass
class BenchmarkResult:
    """One resolver decision compared against the golden expectation."""

    pair_id: str
    category: str
    expected_decision: str
    actual_decision: str
    expected_canonical: str | None
    actual_canonical: str | None
    correct: bool


def load_dataset(path: Path) -> dict[str, Any]:
    """Load and validate the golden resolution dataset."""
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = data["existing_entities"]
    pairs = data["pairs"]
    ids = {e["id"] for e in existing}
    for pair in pairs:
        decision = pair["expected"]["decision"]
        assert decision in {"MERGE", "SIMILAR", "NEW"}, pair["id"]
        canonical = pair["expected"].get("canonical_id")
        if decision == "NEW":
            assert canonical is None, pair["id"]
        else:
            assert canonical in ids, f"{pair['id']} -> unknown canonical {canonical}"
    return data


def decision_from_resolution(result: ResolutionResult) -> str:
    """Map a resolver decision to the golden dataset's vocabulary."""
    return {
        Resolution.MERGE: "MERGE",
        Resolution.SIMILAR: "SIMILAR",
        Resolution.NEW: "NEW",
    }[result.decision]


async def run_benchmark(
    resolver,
    dataset: dict[str, Any],
    graph_store=None,
) -> list[BenchmarkResult]:
    """Run a resolver over every golden pair.

    The resolver must expose `async resolve(name, entity_type, description,
    graph_store=None) -> ResolutionResult`. The graph store is optional and
    forwarded so EntityResolver-style resolvers can perform exact lookups.
    """
    results: list[BenchmarkResult] = []
    for pair in dataset["pairs"]:
        query = pair["query"]
        expected = pair["expected"]
        result = await resolver.resolve(
            name=query["name"],
            entity_type=query["type"],
            description=query.get("description", ""),
            graph_store=graph_store,
        )
        actual_decision = decision_from_resolution(result)
        actual_canonical = result.existing_entity_id

        if expected["decision"] == "NEW":
            correct = actual_decision == "NEW"
        else:
            correct = (
                actual_decision in {"MERGE", "SIMILAR"}
                and actual_canonical == expected["canonical_id"]
            )

        results.append(
            BenchmarkResult(
                pair_id=pair["id"],
                category=pair["category"],
                expected_decision=expected["decision"],
                actual_decision=actual_decision,
                expected_canonical=expected.get("canonical_id"),
                actual_canonical=actual_canonical,
                correct=correct,
            )
        )
    return results


def score(results: list[BenchmarkResult]) -> dict[str, Any]:
    """Aggregate benchmark results into metrics, per category and overall."""
    overall = _aggregate(results)
    categories: dict[str, dict[str, Any]] = {}
    for category in {r.category for r in results}:
        categories[category] = _aggregate([r for r in results if r.category == category])

    return {
        "overall": overall,
        "by_category": categories,
        "total_pairs": len(results),
    }


def _aggregate(results: list[BenchmarkResult]) -> dict[str, Any]:
    """Compute decision accuracy, entity accuracy, and precision/recall/F1."""
    if not results:
        return {
            "decision_accuracy": 0.0,
            "entity_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "count": 0,
        }

    decision_hits = sum(
        r.actual_decision == r.expected_decision for r in results
    )
    entity_hits = sum(1 for r in results if r.correct)

    positives = sum(1 for r in results if r.expected_decision != "NEW")
    found = sum(
        1
        for r in results
        if r.expected_decision != "NEW" and r.actual_canonical == r.expected_canonical
    )
    returned = sum(
        1
        for r in results
        if r.expected_decision != "NEW" and r.actual_canonical is not None
    )

    precision = found / returned if returned else 0.0
    recall = found / positives if positives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "decision_accuracy": round(decision_hits / len(results), 3),
        "entity_accuracy": round(entity_hits / len(results), 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "count": len(results),
    }


def format_report(metrics: dict[str, Any]) -> str:
    """Render metrics as a human-readable report."""
    lines = ["Entity-Resolution Benchmark", "========================="]
    overall = metrics["overall"]
    lines.append(
        f"Overall ({overall['count']} pairs): "
        f"decision_acc={overall['decision_accuracy']:.3f} "
        f"entity_acc={overall['entity_accuracy']:.3f} "
        f"P={overall['precision']:.3f} R={overall['recall']:.3f} F1={overall['f1']:.3f}"
    )
    lines.append("")
    for category, m in sorted(metrics["by_category"].items()):
        lines.append(
            f"  {category:<12} n={m['count']:>2} "
            f"decision_acc={m['decision_accuracy']:.3f} "
            f"F1={m['f1']:.3f}"
        )
    return "\n".join(lines)


# ─── Deterministic synthetic stores (no external services) ───────────────


class DeterministicEmbedder:
    """A reproducible stand-in for real embedding providers.

    Normalizes text (lowercase, punctuation/space removal) then builds a
    weighted bag of character n-grams, which captures both spelling typos and
    formatting differences well enough to exercise the resolver's thresholds.
    """

    _WORD_RE = re.compile(r"[^a-z0-9]+")

    async def embed_single(self, text: str) -> Counter:
        return self.embed(text)

    def embed(self, text: str) -> Counter:
        norm = self._WORD_RE.sub("", text.lower())
        counts: Counter = Counter()
        for n in (1, 2, 3):
            for i in range(len(norm) - n + 1):
                counts[f"{n}:{norm[i:i + n]}"] += 1
        return counts


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b[k] for k, v in a.items())
    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


class SyntheticGraphStore:
    """Exact case-insensitive name lookup over the dataset's existing entities."""

    def __init__(self, existing: list[dict[str, Any]]):
        self.by_name = {e["name"].lower(): e for e in existing}
        self.entities = existing

    async def get_entity(self, name: str) -> dict[str, Any] | None:
        entity = self.by_name.get(name.lower())
        if not entity:
            return None
        return {
            "id": entity["id"],
            "name": entity["name"],
            "qdrant_id": entity["id"],
        }


class SyntheticVectorStore:
    """Cosine-similarity search over pre-computed entity embeddings.

    Mirrors the real Qdrant entity schema: every entity point carries
    ``payload["type"] == "entity"`` (the resolver filters with
    ``filter_type="entity"``); the semantic entity kind ("platform", "tool")
    is stored separately under ``entity_type``.
    """

    def __init__(self, existing: list[dict[str, Any]], embedder: DeterministicEmbedder):
        self.points = []
        for e in existing:
            text = " ".join(
                [e["name"], e.get("type", ""), e.get("description", "")]
            )
            self.points.append({
                "id": e["id"],
                "embedding": embedder.embed(text),
                "payload": {
                    "name": e["name"],
                    "type": "entity",
                    "entity_type": e.get("type"),
                    "node_id": e["id"],
                },
            })

    def search_similar(
        self,
        query_vector: Counter,
        limit: int = 10,
        filter_type: str | None = None,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        scored = []
        for p in self.points:
            if filter_type and p["payload"].get("type") != filter_type:
                continue
            score = _cosine(query_vector, p["embedding"])
            if score >= score_threshold:
                scored.append({
                    "id": p["id"],
                    "score": score,
                    "payload": p["payload"],
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]


def build_synthetic_resolver(dataset: dict[str, Any]):
    """Build a live EntityResolver wired to deterministic stores for the dataset."""
    from src.graph.entity_resolver import EntityResolver

    embedder = DeterministicEmbedder()
    graph = SyntheticGraphStore(dataset["existing_entities"])
    vector = SyntheticVectorStore(dataset["existing_entities"], embedder)
    resolver = EntityResolver(vector_store=vector, embedder=embedder)
    return resolver, graph


async def run_synthetic_benchmark() -> dict[str, Any]:
    """Run the real resolver against the golden dataset with fake stores."""
    dataset = load_dataset(GOLDEN_FIXTURE)
    resolver, graph = build_synthetic_resolver(dataset)
    results = await run_benchmark(resolver, dataset, graph_store=graph)
    return score(results)


__all__ = [
    "GOLDEN_FIXTURE",
    "BenchmarkResult",
    "load_dataset",
    "decision_from_resolution",
    "run_benchmark",
    "score",
    "format_report",
    "run_synthetic_benchmark",
    "build_synthetic_resolver",
]


def main() -> None:
    """CLI entry point: print the synthetic benchmark report."""
    import asyncio

    report = format_report(asyncio.run(run_synthetic_benchmark()))
    sys.stdout.write(report + "\n")


if __name__ == "__main__":
    main()
