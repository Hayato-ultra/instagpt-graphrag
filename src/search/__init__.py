"""Hybrid search — combines vector, fulltext, and graph signals.

Search pipeline:
1. Vector similarity (Qdrant) — semantic match
2. Fulltext search (Neo4j) — lexical match
3. Graph relationships (Neo4j) — connectivity boost
4. Reranking — combine scores with weights
5. Adaptive weighting — adjust weights based on query type (TODO #37)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from loguru import logger


@dataclass
class SearchResult:
    """Search result with combined score."""
    id: str
    name: str
    description: str
    entity_type: str
    score: float
    source: str  # "vector", "fulltext", "graph", "combined"
    metadata: dict = None


def _classify_query(query: str) -> str:
    """Classify query type for adaptive weighting (TODO #37)."""
    q = query.lower().strip()
    # Exact entity name lookup
    if len(q.split()) <= 2 and not any(w in q for w in ["how", "what", "why", "where", "when", "which"]):
        return "lookup"
    # Conceptual/semantic query
    if any(w in q for w in ["similar", "like", "about", "related to", "concept"]):
        return "semantic"
    # Relationship query
    if any(w in q for w in ["connect", "depend", "use", "call", "import", "inherit"]):
        return "relationship"
    # Default balanced
    return "balanced"


class HybridSearcher:
    """Search across vector, fulltext, and graph stores.
    
    Weights are adjusted dynamically based on query type (TODO #37):
    - lookup: favor fulltext (exact name match)
    - semantic: favor vector (meaning-based)
    - relationship: favor graph (connections)
    - balanced: default weights
    """
    
    # Default weights
    VECTOR_WEIGHT = 0.5
    FULLTEXT_WEIGHT = 0.3
    GRAPH_WEIGHT = 0.2
    
    # Adaptive weight profiles
    WEIGHT_PROFILES = {
        "lookup":     {"vector": 0.2, "fulltext": 0.7, "graph": 0.1},
        "semantic":   {"vector": 0.7, "fulltext": 0.2, "graph": 0.1},
        "relationship": {"vector": 0.2, "fulltext": 0.1, "graph": 0.7},
        "balanced":   {"vector": 0.5, "fulltext": 0.3, "graph": 0.2},
    }
    
    def __init__(self, vector_store, graph_store, embedder=None):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.embedder = embedder
    
    async def search(
        self,
        query: str,
        limit: int = 20,
        use_vector: bool = True,
        use_fulltext: bool = True,
        use_graph: bool = True,
        adaptive: bool = True,
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining vector, fulltext, and graph signals.
        
        Args:
            query: search query.
            limit: max results.
            use_vector: enable vector search.
            use_fulltext: enable fulltext search.
            use_graph: enable graph boost.
            adaptive: adjust weights based on query type (TODO #37).
        """
        # Adaptive weighting (TODO #37)
        if adaptive:
            query_type = _classify_query(query)
            weights = self.WEIGHT_PROFILES.get(query_type, self.WEIGHT_PROFILES["balanced"])
            vec_w = weights["vector"]
            ft_w = weights["fulltext"]
            gr_w = weights["graph"]
        else:
            query_type = "balanced"
            vec_w = self.VECTOR_WEIGHT
            ft_w = self.FULLTEXT_WEIGHT
            gr_w = self.GRAPH_WEIGHT
        candidates = {}  # entity_id -> {data, scores}
        
        # 1. Vector similarity search
        if use_vector and self.embedder:
            try:
                vector_results = await self._vector_search(query, limit=limit * 2)
                for r in vector_results:
                    eid = r["id"]
                    if eid not in candidates:
                        candidates[eid] = {"data": r, "scores": {}}
                    candidates[eid]["scores"]["vector"] = r.get("score", 0.0)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        
        # 2. Fulltext search (Neo4j)
        if use_fulltext:
            try:
                fulltext_results = await self._fulltext_search(query, limit=limit * 2)
                for r in fulltext_results:
                    eid = r.get("id", r.get("name", ""))
                    if eid not in candidates:
                        candidates[eid] = {"data": r, "scores": {}}
                    candidates[eid]["scores"]["fulltext"] = 1.0  # Binary match
            except Exception as e:
                logger.warning(f"Fulltext search failed: {e}")
        
        # 3. Graph relationship boost
        if use_graph and candidates:
            try:
                await self._graph_boost(candidates)
            except Exception as e:
                logger.warning(f"Graph boost failed: {e}")
        
        # 4. Rerank by combined score
        results = self._rerank(candidates, limit, vec_w, ft_w, gr_w)
        
        return results
    
    async def _vector_search(self, query: str, limit: int) -> List[Dict]:
        """Semantic search via Qdrant."""
        if not self.embedder:
            return []
        
        embedding = await self.embedder.embed_single(query)
        
        results = self.vector_store.search_similar(
            query_vector=embedding,
            limit=limit,
            filter_type="entity",
            filter_field="node_type",
            score_threshold=0.3,
        )
        
        return [
            {
                "id": r["payload"].get("name", ""),
                "name": r["payload"].get("name", ""),
                "description": r["payload"].get("description", ""),
                "entity_type": r["payload"].get("type", ""),
                "score": r["score"],
                "source": "vector",
            }
            for r in results
        ]
    
    async def _fulltext_search(self, query: str, limit: int) -> List[Dict]:
        """Lexical search via Neo4j fulltext index."""
        results = await self.graph_store.search_entities(query, limit=limit)
        return [
            {
                "id": r.get("name", ""),
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "entity_type": r.get("type", ""),
                "score": 1.0,
                "source": "fulltext",
            }
            for r in results
        ]
    
    async def _graph_boost(self, candidates: Dict):
        """Boost score for entities with many connections."""
        for eid in list(candidates.keys())[:20]:  # Limit to avoid too many queries
            try:
                related = await self.graph_store.get_related(eid, limit=5)
                if related:
                    # Boost based on number of connections
                    boost = min(len(related) * 0.05, 0.3)  # Max 0.3 boost
                    candidates[eid]["scores"]["graph"] = boost
            except Exception:
                pass
    
    def _rerank(self, candidates: Dict, limit: int, vec_w: float = 0.5, ft_w: float = 0.3, gr_w: float = 0.2) -> List[Dict]:
        """Combine scores and return top results."""
        scored = []
        for eid, data in candidates.items():
            scores = data["scores"]
            combined = (
                scores.get("vector", 0.0) * vec_w +
                scores.get("fulltext", 0.0) * ft_w +
                scores.get("graph", 0.0) * gr_w
            )
            scored.append({
                **data["data"],
                "score": combined,
                "score_breakdown": scores,
                "source": "combined",
            })
        
        # Sort by combined score
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        return scored[:limit]
