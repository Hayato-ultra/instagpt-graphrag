import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from src.config import get_settings
from src.models import (
    ProcessingResult, 
    PipelineStage,
    ExtractedContent,
    DocumentChunk,
    EnrichedEntity,
    CategorizedItem,
)
from src.extractor import ContentExtractor, SemanticChunker
from src.vector_store import Embedder, VectorStore
from src.enrichment import EnrichmentPipeline
from src.categorizer import Categorizer
from src.output_generator import generate_outputs
from src.neo4j_graph_store import Neo4jGraphStore, create_graph_store
from loguru import logger


settings = get_settings()


@dataclass
class PipelineResult:
    success: bool
    url: str
    processing_result: Optional[ProcessingResult] = None
    markdown_path: Optional[str] = None
    json_path: Optional[str] = None
    graph_stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class KnowledgeGraphPipeline:
    """Main pipeline orchestrating all stages."""
    
    def __init__(self):
        self.extractor = ContentExtractor()
        self.chunker = SemanticChunker(
            chunk_size=settings.MAX_CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            min_chunk_size=settings.MIN_CHUNK_SIZE,
        )
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        self.enrichment = EnrichmentPipeline()
        self.categorizer = Categorizer()
        self.graph_store = None  # Initialized in initialize()
        self._initialized = False
    
    async def initialize(self):
        """Initialize async components (Neo4j connection)."""
        if self._initialized:
            return
        
        logger.info("Initializing Neo4j graph store...")
        self.graph_store = await create_graph_store()
        self.graph_store.set_embedder(self.embedder)
        self._initialized = True
        logger.success("Neo4j graph store initialized")
    
    async def close(self):
        """Cleanup resources."""
        await self.extractor.close()
        await self.enrichment.close()
        if self.vector_store.client:
            await self.vector_store.client.close()
        if self.embedder.client:
            await self.embedder.client.close()
        await self.categorizer.close()
        if self.graph_store:
            await self.graph_store.close()
    
    async def process_url(self, url: str) -> PipelineResult:
        """Process a single URL through the full pipeline."""
        start_time = time.time()
        logger.info(f"Starting pipeline for: {url}")
        
        try:
            # Stage 1: Extract
            logger.info("Stage 1: Extracting content")
            extracted = await self.extractor.extract(url)
            stages = [PipelineStage.EXTRACT]
            
            # Stage 2: Chunk
            logger.info("Stage 2: Chunking content")
            chunks = self.chunker.chunk(extracted.raw_text, extracted.title)
            for chunk in chunks:
                chunk.metadata["source_url"] = str(url)
            stages.append(PipelineStage.ENRICH)
            
            # Stage 3: Embed chunks
            logger.info("Stage 3: Embedding chunks")
            chunks = await self.embedder.embed_chunks(chunks)
            
            # Store chunks in vector DB
            self.vector_store.upsert_chunks(chunks, str(url))
            
            # Stage 4: Enrich (detect entities + web search)
            logger.info("Stage 4: Enriching with entity detection & web search")
            entities = []
            for chunk in chunks:
                chunk_entities = await self.enrichment.enrich_chunk(chunk)
                entities.extend(chunk_entities)
            
            # Deduplicate entities by name
            entities = self._deduplicate_entities(entities)
            stages.append(PipelineStage.CATEGORIZE)
            
            # Stage 5: Categorize
            logger.info("Stage 5: Categorizing entities")
            categorized = await self.categorizer.categorize(entities)
            stages.append(PipelineStage.FORMAT)
            
            # Stage 6: Generate outputs
            logger.info("Stage 6: Generating outputs")
            md_path, json_path = generate_outputs(
                categorized, 
                str(url), 
                settings.OUTPUT_DIR
            )
            
            # Stage 7: Update neural graph
            logger.info("Stage 7: Updating neural graph")
            merge_result = await self.graph_store.upsert_knowledge(categorized)
            stages.append(PipelineStage.GRAPH_UPDATE)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = ProcessingResult(
                url=url,
                success=True,
                extracted_content=extracted,
                chunks=chunks,
                entities=entities,
                categorized_items=categorized,
                processing_time_ms=processing_time,
                stages_completed=stages
            )
            
            logger.success(f"Pipeline completed in {processing_time}ms: {len(entities)} entities, {len(categorized)} categorized")
            
            return PipelineResult(
                success=True,
                url=str(url),
                processing_result=result,
                markdown_path=str(md_path),
                json_path=str(json_path),
                graph_stats=merge_result.__dict__
            )
            
        except Exception as e:
            logger.error(f"Pipeline failed for {url}: {e}")
            processing_time = int((time.time() - start_time) * 1000)
            
            result = ProcessingResult(
                url=url,
                success=False,
                error=str(e),
                processing_time_ms=processing_time,
                stages_completed=stages if 'stages' in dir() else []
            )
            
            return PipelineResult(
                success=False,
                url=str(url),
                processing_result=result,
                error=str(e)
            )
    
    async def process_batch(
        self, 
        urls: List[str], 
        max_concurrent: int = None
    ) -> List[PipelineResult]:
        """Process multiple URLs concurrently."""
        max_concurrent = max_concurrent or settings.MAX_CONCURRENT_URLS
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(url: str) -> PipelineResult:
            async with semaphore:
                return await self.process_url(url)
        
        tasks = [process_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                final_results.append(PipelineResult(
                    success=False,
                    url=url,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    def _deduplicate_entities(self, entities: List[EnrichedEntity]) -> List[EnrichedEntity]:
        """Deduplicate entities by name (case-insensitive)."""
        seen = {}
        for entity in entities:
            key = entity.name.lower()
            if key not in seen or entity.confidence > seen[key].confidence:
                seen[key] = entity
        return list(seen.values())


async def main():
    """Test the pipeline."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.pipeline <url> [url2] [url3] ...")
        return
    
    urls = sys.argv[1:]
    pipeline = KnowledgeGraphPipeline()
    
    try:
        await pipeline.initialize()
        
        if len(urls) == 1:
            result = await pipeline.process_url(urls[0])
            if result.success:
                print(f"\n✅ Success!")
                print(f"   Markdown: {result.markdown_path}")
                print(f"   JSON: {result.json_path}")
                print(f"   Graph: {result.graph_stats}")
            else:
                print(f"\n❌ Failed: {result.error}")
        else:
            results = await pipeline.process_batch(urls)
            print(f"\n📊 Batch Results ({len(results)} URLs):")
            for r in results:
                status = "✅" if r.success else "❌"
                print(f"  {status} {r.url}")
                if r.success:
                    print(f"      Entities: {len(r.processing_result.entities)}")
                    print(f"      Categorized: {len(r.processing_result.categorized_items)}")
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())