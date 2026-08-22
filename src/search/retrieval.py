"""Retrieval quality and context window management (TODO #55, #56).

Ensures retrieved context is relevant, diverse, and fits within LLM limits.
"""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class RetrievalConfig:
    """Configuration for retrieval quality."""
    max_context_tokens: int = 8000
    min_relevance_score: float = 0.3
    max_results: int = 20
    diversity_weight: float = 0.2  # Boost for diverse entity types


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token)."""
    return len(text) // 4


def _entity_type_diversity(results: list[dict]) -> float:
    """Calculate type diversity score (0-1)."""
    if not results:
        return 0.0
    types = set(r.get("entity_type", "unknown") for r in results)
    return min(len(types) / 5.0, 1.0)  # 5+ types = max diversity


def filter_and_rank_results(
    results: list[dict],
    config: RetrievalConfig | None = None,
) -> list[dict]:
    """Filter and rank retrieval results for quality (TODO #55).

    Args:
        results: raw search results with 'score' and 'entity_type'.
        config: retrieval configuration.

    Returns:
        Filtered and ranked results.
    """
    cfg = config or RetrievalConfig()

    # 1. Filter by minimum relevance
    filtered = [r for r in results if r.get("score", 0) >= cfg.min_relevance_score]

    # 2. Apply diversity boost
    if cfg.diversity_weight > 0:
        type_counts: dict[str, int] = {}
        for r in filtered:
            t = r.get("entity_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        for r in filtered:
            t = r.get("entity_type", "unknown")
            # Boost underrepresented types
            if type_counts[t] <= 1:
                r["score"] = r.get("score", 0) * (1 + cfg.diversity_weight)

    # 3. Sort by adjusted score
    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 4. Limit results
    return filtered[:cfg.max_results]


def fit_context_window(
    results: list[dict],
    max_tokens: int = 8000,
    description_key: str = "description",
) -> list[dict]:
    """Fit results within context window budget (TODO #56).

    Greedily adds results until token budget is exhausted.
    """
    selected = []
    used_tokens = 0

    for r in results:
        desc = r.get(description_key, "")
        est_tokens = _estimate_tokens(r.get("name", "")) + _estimate_tokens(desc) + 20

        if used_tokens + est_tokens <= max_tokens:
            selected.append(r)
            used_tokens += est_tokens
        else:
            break

    logger.debug(
        f"Context window: {len(selected)}/{len(results)} results "
        f"fit ({used_tokens}/{max_tokens} tokens)"
    )
    return selected
