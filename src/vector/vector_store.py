import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

import openai
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import Distance, VectorParams, PointStruct

from src.config import get_settings
from src.config.models import DocumentChunk, EnrichedEntity
from loguru import logger


settings = get_settings()


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    NVIDIA = "nvidia"
    GOOGLE = "google"


@dataclass
class EmbeddingConfig:
    """Configuration for an embedding model."""
    provider: EmbeddingProvider
    model: str
    dimensions: int
    max_batch_size: int = 2048
    cost_per_1k_tokens: float = 0.0


# Embedding model registry
EMBEDDING_MODELS = {
    # OpenAI
    "text-embedding-3-small": EmbeddingConfig(EmbeddingProvider.OPENAI, "text-embedding-3-small", 1536, 2048, 0.00002),
    "text-embedding-3-large": EmbeddingConfig(EmbeddingProvider.OPENAI, "text-embedding-3-large", 3072, 2048, 0.00013),
    "text-embedding-ada-002": EmbeddingConfig(EmbeddingProvider.OPENAI, "text-embedding-ada-002", 1536, 2048, 0.0001),
    # NVIDIA
    "nvidia/nv-embedqa-e5-v5": EmbeddingConfig(EmbeddingProvider.NVIDIA, "nvidia/nv-embedqa-e5-v5", 1024, 512, 0.0),
    "nvidia/nv-embed-v1": EmbeddingConfig(EmbeddingProvider.NVIDIA, "nvidia/nv-embed-v1", 4096, 512, 0.0),
    # Google
    "gemini-embedding-001": EmbeddingConfig(EmbeddingProvider.GOOGLE, "gemini-embedding-001", 768, 2048, 0.0),
}


class Embedder:
    def __init__(self):
        self.openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.nvidia_client = None
        self.google_client = None
        
        if getattr(settings, 'NVIDIA_API_KEY', None):
            self.nvidia_client = openai.AsyncOpenAI(
                api_key=settings.NVIDIA_API_KEY,
                base_url="https://integrate.api.nvidia.com/v1"
            )
        if getattr(settings, 'GOOGLE_API_KEY', None):
            self.google_client = openai.AsyncOpenAI(
                api_key=settings.GOOGLE_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
        
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimensions = settings.OPENAI_EMBEDDING_DIM
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts with fallback providers."""
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = await self._embed_batch_with_fallback(batch)
            all_embeddings.extend(embeddings)
        
        return all_embeddings

    async def _embed_batch_with_fallback(self, batch: List[str]) -> List[List[float]]:
        """Try embedding with fallback providers."""
        # Try OpenAI first
        try:
            response = await self.openai_client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.warning(f"OpenAI embedding failed: {e}")
        
        # Try NVIDIA (uses different model names, returns 1024 dim by default)
        if self.nvidia_client:
            try:
                response = await self.nvidia_client.embeddings.create(
                    model="nvidia/nv-embedqa-e5-v5",
                    input=batch,
                    encoding_format="float",
                    extra_body={"input_type": "query"}
                )
                embeddings = [item.embedding for item in response.data]
                # Pad or truncate to match expected dimensions
                return [self._adjust_dimensions(e) for e in embeddings]
            except Exception as e:
                logger.warning(f"NVIDIA embedding failed: {e}")
        
        # Try Google (gemini-embedding-001 returns 768 dim by default)
        if self.google_client:
            try:
                response = await self.google_client.embeddings.create(
                    model="gemini-embedding-001",
                    input=batch
                )
                embeddings = [item.embedding for item in response.data]
                # Pad or truncate to match expected dimensions
                return [self._adjust_dimensions(e) for e in embeddings]
            except Exception as e:
                logger.warning(f"Google embedding failed: {e}")
        
        raise Exception("All embedding providers failed")
    
    def _adjust_dimensions(self, embedding: List[float]) -> List[float]:
        """No-op — never pad or truncate embeddings.
        
        Each embedding provider returns its native dimension:
        - OpenAI text-embedding-3-small: 1536
        - NVIDIA nv-embedqa-e5-v5: 1024
        - Google gemini-embedding-001: 768
        
        Padding with zeros makes vectors mathematically incomparable.
        Instead, use separate Qdrant collections per embedding model,
        or stick to one provider consistently.
        """
        return embedding

    async def embed_single(self, text: str) -> List[float]:
        """Embed a single text."""
        return (await self.embed_texts([text]))[0]

    async def embed_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Embed all chunks in place."""
        texts = [chunk.text for chunk in chunks]
        embeddings = await self.embed_texts(texts)
        
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        return chunks


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None
        )
        self.collection_name = settings.QDRANT_COLLECTION
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]
        
        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.OPENAI_EMBEDDING_DIM,
                    distance=Distance.COSINE
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                    max_segment_size=20000
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100
                )
            )
            logger.info(f"Created collection: {self.collection_name}")

    def upsert_chunks(self, chunks: List[DocumentChunk], source_url: str) -> int:
        """Upsert document chunks."""
        points = []
        for chunk in chunks:
            if chunk.embedding is None:
                logger.warning(f"Chunk {chunk.id} has no embedding, skipping")
                continue
            
            points.append(PointStruct(
                id=chunk.id,
                vector=chunk.embedding,
                payload={
                    "text": chunk.text,
                    "source_url": source_url,
                    "chunk_index": chunk.chunk_index,
                    "header_path": chunk.metadata.get("header_path", ""),
                    "header_level": chunk.metadata.get("header_level", 0),
                    "token_count": chunk.token_count,
                    "type": "document_chunk"
                }
            ))
        
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Upserted {len(points)} chunks for {source_url}")
        
        return len(points)

    async def upsert_entities(self, entities: List[EnrichedEntity], embedder=None) -> int:
        """Upsert enriched entities with real embeddings.
        
        Embedding is generated from canonical entity representation:
        name + type + description (not padded placeholders).
        """
        if not entities:
            return 0
            
        # Generate embeddings for all entities
        texts = [
            f"{e.name} {e.type.value} {e.description}"
            for e in entities
        ]
        
        if embedder:
            try:
                embeddings = await embedder.embed_texts(texts)
            except Exception as e:
                logger.error(f"Failed to embed entities: {e}")
                return 0
        else:
            logger.warning("No embedder provided, cannot upsert entities")
            return 0
        
        points = []
        for entity, embedding in zip(entities, embeddings):
            points.append(PointStruct(
                id=f"entity-{entity.name}-{uuid4().hex[:8]}",
                vector=embedding,
                payload={
                    "name": entity.name,
                    "type": entity.type.value,
                    "description": entity.description,
                    "web_info": entity.web_info,
                    "similar_tools": entity.similar_tools,
                    "source_url": entity.source_url,
                    "source_chunk_id": entity.source_chunk_id,
                    "confidence": entity.confidence,
                    "type": "entity"
                }
            ))
        
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        return len(points)

    def search_similar(
        self,
        query_vector: List[float],
        limit: int = 10,
        filter_type: Optional[str] = None,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        query_filter = None
        if filter_type:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="type", match=models.MatchValue(value=filter_type))]
            )
        
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold,
            with_payload=True
        )
        
        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload
            }
            for r in results.points
        ]

    def search_hybrid(
        self,
        query_vector: List[float],
        query_text: str,
        limit: int = 10,
        vector_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining vector and text search."""
        # Vector search
        vector_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit * 2,
            with_payload=True
        )
        
        # Text search (using payload text)
        # Note: Qdrant doesn't have native BM25, would need separate index
        # For now, return vector results
        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload
            }
            for r in vector_results[:limit]
        ]

    def get_by_source_url(self, source_url: str) -> List[Dict[str, Any]]:
        """Get all points from a source URL."""
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="source_url", match=models.MatchValue(value=source_url))]
            ),
            limit=1000,
            with_payload=True
        )
        
        return [
            {"id": r.id, "payload": r.payload}
            for r in results[0]
        ]

    def delete_by_source_url(self, source_url: str) -> int:
        """Delete all points from a source URL."""
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="source_url", match=models.MatchValue(value=source_url))]
                )
            )
        )
        return result.operation_id

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection statistics."""
        info = self.client.get_collection(self.collection_name)
        return {
            "name": info.config.params.vectors.size,
            "vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "status": info.status
        }