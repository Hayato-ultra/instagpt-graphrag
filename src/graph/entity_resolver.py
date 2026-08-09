"""Centralized entity resolution — single source of truth for deduplication.

Both Neo4jGraphStore and NetworkXStore consume this resolver's decisions
instead of implementing their own dedup logic.

Rules:
1. One Entity = one real-world concept (unique by name, case-insensitive)
2. Embedding similarity for fuzzy dedup (0.92 = same, 0.85-0.92 = similar)
3. Entity connects to multiple Topics (not duplicate nodes)
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional
from loguru import logger


class Resolution(Enum):
    """Entity resolution decision."""
    MERGE = "merge"           # Same entity — update existing
    SIMILAR = "similar"       # Similar entity — create + SIMILAR_TO edge
    NEW = "new"               # New entity — create fresh node


@dataclass
class ResolutionResult:
    """Result of entity resolution."""
    decision: Resolution
    existing_entity_id: Optional[str] = None
    existing_entity_name: Optional[str] = None
    similarity_score: float = 0.0
    qdrant_id: Optional[str] = None


class EntityResolver:
    """Authoritative entity deduplication.
    
    Consumed by graph stores during upsert_knowledge().
    Uses Qdrant for vector similarity + Neo4j for exact name lookup.
    """
    
    SAME_ENTITY_THRESHOLD = 0.92
    SIMILAR_ENTITY_THRESHOLD = 0.85
    
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
        2. Embedding similarity >= 0.92 → MERGE
        3. Embedding similarity 0.85-0.92 → SIMILAR
        4. No match → NEW
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
        
        similar = self.vector_store.search_similar(
            query_vector=embedding,
            limit=5,
            filter_type="entity",
            score_threshold=self.SIMILAR_ENTITY_THRESHOLD,
        )
        
        if not similar:
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
            return ResolutionResult(
                decision=Resolution.SIMILAR,
                existing_entity_id=best["payload"].get("node_id"),
                existing_entity_name=best["payload"].get("name"),
                similarity_score=score,
                qdrant_id=best["id"],
            )
        
        return ResolutionResult(decision=Resolution.NEW)
