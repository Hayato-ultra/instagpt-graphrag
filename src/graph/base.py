"""Abstract base class for graph store implementations.

Target architecture:
- PostgreSQL: application/job state, sources, content metadata
- Neo4j: entity relationships, topic hierarchy, knowledge graph
- Qdrant: vector embeddings, semantic search
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from src.config.models import (
    CategorizedItem,
    EnrichedEntity,
    ExtractedRelationship,
)


@dataclass
class MergeResult:
    """Result of a graph merge operation."""
    new_nodes: int = 0
    updated_nodes: int = 0
    merged_edges: int = 0
    errors: List[str] = field(default_factory=list)


class GraphStore(ABC):
    """Abstract interface for graph store implementations.

    Production: Neo4jGraphStore (Neo4j + Qdrant vectors)
    Testing: NetworkXStore (in-memory, no external deps)
    """

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to the graph store."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close connection to the graph store."""
        ...

    @abstractmethod
    def set_embedder(self, embedder) -> None:
        """Set the embedding model for vector operations."""
        ...

    @abstractmethod
    async def upsert_knowledge(
        self,
        items: List[CategorizedItem],
        relationships: List[ExtractedRelationship] = None,
    ) -> MergeResult:
        """Upsert categorized items and relationships into the graph.

        Deduplication rules:
        1. One Entity = one real-world concept (unique by name, case-insensitive)
        2. Entity connects to multiple Topics/SubTopics (not duplicate nodes)
        3. Embedding similarity used for fuzzy dedup (threshold: 0.92 = same, 0.85-0.92 = similar)
        """
        ...

    @abstractmethod
    async def get_entity(self, name: str) -> Optional[Dict]:
        """Get a single entity by name."""
        ...

    @abstractmethod
    async def get_related(
        self, name: str, relation: str = None, limit: int = 10
    ) -> List[Dict]:
        """Get entities related to the given entity."""
        ...

    @abstractmethod
    async def search_entities(
        self, query_text: str, limit: int = 10
    ) -> List[Dict]:
        """Search entities by text query."""
        ...

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        ...

    @abstractmethod
    async def export_graph(self, format: str = "cypher") -> str:
        """Export graph in the specified format."""
        ...
