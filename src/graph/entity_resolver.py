"""Centralized entity resolution — single source of truth for deduplication.

Both Neo4jGraphStore and NetworkXStore consume this resolver's decisions
instead of implementing their own dedup logic.

Rules:
1. One Entity = one real-world concept (unique by name, case-insensitive)
2. Embedding similarity for fuzzy dedup (0.92 = same, 0.85-0.92 = similar)
3. Entity connects to multiple Topics (not duplicate nodes)
"""

import asyncio
import re
from dataclasses import dataclass
from enum import Enum

from loguru import logger


def normalize_name(name: str) -> str:
    """Normalize an entity name for alias comparisons.

    Lowercases and strips spacing, punctuation, and other non-alphanumeric
    characters so "VS Code", "VSCode", and "vs-code" all compare equal.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,
                cur[j - 1] + 1,
                prev[j - 1] + (ca != cb),
            ))
        prev = cur
    return prev[-1]


def names_align(a: str, b: str, max_typos: int = 2, min_prefix_len: int = 3) -> bool:
    """Check whether two normalized names likely refer to the same entity.

    Returns True when the names differ only by:
    - a small number of typos (edit distance <= ``max_typos``), or
    - one being an abbreviation/compound of the other (prefix relation with a
      non-trivial shorter side, e.g. "postgres" vs "postgresql",
      "aws" vs "awscloud").
    """
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if _edit_distance(na, nb) <= max_typos:
        return True
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(short) >= min_prefix_len and long.startswith(short)


class Resolution(Enum):
    """Entity resolution decision."""
    MERGE = "merge"           # Same entity — update existing
    SIMILAR = "similar"       # Similar entity — create + SIMILAR_TO edge
    NEW = "new"               # New entity — create fresh node


@dataclass
class ResolutionResult:
    """Result of entity resolution."""
    decision: Resolution
    existing_entity_id: str | None = None
    existing_entity_name: str | None = None
    similarity_score: float = 0.0
    qdrant_id: str | None = None


class EntityResolver:
    """Authoritative entity deduplication.

    Consumed by graph stores during upsert_knowledge().
    Uses Qdrant for vector similarity + Neo4j for exact name lookup + graph context.
    """

    SAME_ENTITY_THRESHOLD = 0.92
    SIMILAR_ENTITY_THRESHOLD = 0.85
    ALIAS_SEARCH_THRESHOLD = 0.60

    def __init__(self, vector_store, embedder=None):
        self.vector_store = vector_store
        self.embedder = embedder

    async def resolve(
        self,
        name: str,
        entity_type: str,
        description: str,
        graph_store=None,
    ) -> ResolutionResult:
        """Resolve entity identity against existing entities.

        Priority:
        1. Exact name match (case-insensitive) → MERGE
        2. Normalized-name alias (e.g. "VSCode" ≈ "VS Code") → MERGE
        3. Embedding similarity >= 0.92 → MERGE
        4. Embedding similarity 0.85-0.92 → SIMILAR (or MERGE if names align:
           typos like "Apprite"/"Appwrite", or abbreviations/compounds like
           "postgres"/"PostgreSQL" or "AWS"/"AWS Cloud")
        5. Graph similarity (shared relationships) → SIMILAR
        6. No match → NEW
        """
        # 1. Exact name match via graph store (if available)
        if graph_store:
            existing = await graph_store.get_entity(name)
            if existing:
                return ResolutionResult(
                    decision=Resolution.MERGE,
                    existing_entity_id=existing.get("id"),
                    existing_entity_name=existing.get("name"),
                    similarity_score=1.0,
                    qdrant_id=existing.get("qdrant_id"),
                )

        # 2. Embedding similarity via Qdrant
        if not self.embedder:
            logger.warning("No embedder — cannot do fuzzy dedup, returning NEW")
            return ResolutionResult(decision=Resolution.NEW)

        try:
            embedding = await self.embedder.embed_single(
                f"{name} {entity_type} {description}"
            )
        except Exception as e:
            logger.error(f"Embedding failed for entity '{name}': {e}")
            return ResolutionResult(decision=Resolution.NEW)

        similar = await asyncio.to_thread(
            self.vector_store.search_similar,
            query_vector=embedding,
            limit=10,
            filter_type="entity",
            score_threshold=self.ALIAS_SEARCH_THRESHOLD,
        )

        # 2a. Normalized-name alias: "VSCode" == "VS Code" (> spacing/case/punct differences)
        norm_query = normalize_name(name)
        for cand in similar:
            cand_name = (cand.get("payload") or {}).get("name", "")
            if cand_name and normalize_name(cand_name) == norm_query:
                return ResolutionResult(
                    decision=Resolution.MERGE,
                    existing_entity_id=cand["payload"].get("node_id"),
                    existing_entity_name=cand_name,
                    similarity_score=cand["score"],
                    qdrant_id=cand["id"],
                )

        if not similar:
            # 5. Graph-based similarity: check shared relationships (TODO #34)
            if graph_store:
                graph_result = await self._graph_similarity(name, entity_type, graph_store)
                if graph_result:
                    return graph_result
            return ResolutionResult(decision=Resolution.NEW)

        best = similar[0]
        score = best["score"]

        if score >= self.SAME_ENTITY_THRESHOLD:
            return ResolutionResult(
                decision=Resolution.MERGE,
                existing_entity_id=best["payload"].get("node_id"),
                existing_entity_name=best["payload"].get("name"),
                similarity_score=score,
                qdrant_id=best["id"],
            )
        elif score >= self.SIMILAR_ENTITY_THRESHOLD:
            best_name = best["payload"].get("name")
            if best_name and names_align(name, best_name):
                return ResolutionResult(
                    decision=Resolution.MERGE,
                    existing_entity_id=best["payload"].get("node_id"),
                    existing_entity_name=best_name,
                    similarity_score=score,
                    qdrant_id=best["id"],
                )
            return ResolutionResult(
                decision=Resolution.SIMILAR,
                existing_entity_id=best["payload"].get("node_id"),
                existing_entity_name=best_name,
                similarity_score=score,
                qdrant_id=best["id"],
            )

        # 5. Graph-based similarity: check shared relationships (TODO #34)
        if graph_store:
            graph_result = await self._graph_similarity(name, entity_type, graph_store)
            if graph_result:
                return graph_result

        return ResolutionResult(decision=Resolution.NEW)

    async def _graph_similarity(
        self, name: str, entity_type: str, graph_store
    ) -> ResolutionResult | None:
        """Check graph-based similarity via shared relationships (TODO #34).

        If two entities share many relationships or are closely connected
        in the graph, they might be the same entity.
        """
        try:
            # Find entities with same type
            similar_entities = await graph_store.search_entities(
                name, limit=5
            )

            for candidate in similar_entities:
                cand_name = candidate.get("name", "")
                if not cand_name or cand_name.lower() == name.lower():
                    continue

                # Check if they share the same relationships
                cand_related = await graph_store.get_related(cand_name, limit=10)
                if not cand_related:
                    continue

                # Simple heuristic: if both have similar descriptions, likely same
                cand_desc = candidate.get("description", "")
                if self._descriptions_similar(name, cand_desc):
                    return ResolutionResult(
                        decision=Resolution.SIMILAR,
                        existing_entity_id=candidate.get("id"),
                        existing_entity_name=cand_name,
                        similarity_score=0.7,
                    )

        except Exception as e:
            logger.debug(f"Graph similarity check failed: {e}")

        return None

    def _descriptions_similar(self, name: str, description: str) -> bool:
        """Check if entity name appears in description."""
        if not description:
            return False
        name_lower = name.lower()
        desc_lower = description.lower()
        return name_lower in desc_lower or desc_lower[:20] in name_lower
