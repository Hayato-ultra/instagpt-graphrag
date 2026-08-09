"""Hybrid search — combines vector, fulltext, and graph signals.

Search pipeline:
1. Vector similarity (Qdrant) — semantic match
2. Fulltext search (Neo4j) — lexical match
3. Graph relationships (Neo4j) — connectivity boost
4. Reranking — combine scores with weights
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


class HybridSearcher:
    """Search across vector, fulltext, and graph stores.
    
    Weights:
    - vector: 0.5 (semantic similarity)
    - fulltext: 0.3 (lexical match)
    - graph: 0.2 (relationship connectivity)
    """
    
    VECTOR_WEIGHT = 0.5
    FULLTEXT_WEIGHT = 0.3
    GRAPH_WEIGHT = 0.2
    
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
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining vector, fulltext, and graph signals."""
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
        results = self._rerank(candidates, limit)
        
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
    
    def _rerank(self, candidates: Dict, limit: int) -> List[Dict]:
        """Combine scores and return top results."""
        scored = []
        for eid, data in candidates.items():
            scores = data["scores"]
            combined = (
                scores.get("vector", 0.0) * self.VECTOR_WEIGHT +
                scores.get("fulltext", 0.0) * self.FULLTEXT_WEIGHT +
                scores.get("graph", 0.0) * self.GRAPH_WEIGHT
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
