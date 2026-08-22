"""Knowledge graph pipeline with checkpoint/resume support.

Each stage is independently resumable. Completed stages are never re-run.
URL normalization and content hashing ensure idempotency.
"""
import asyncio
import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from loguru import logger

from src.config import get_settings
from src.config.models import (
    CategorizedItem,
    DocumentChunk,
    EnrichedEntity,
    ExtractedContent,
    ExtractedRelationship,
    ProcessingResult,
)
from src.enrichment import EnrichmentPipeline
from src.enrichment.categorizer import Categorizer
from src.extraction import ContentExtractor, SemanticChunker
from src.graph import Neo4jGraphStore, create_graph_store
from src.graph.entity_resolver import normalize_name
from src.output import generate_outputs
from src.pipeline.recorder import BaseRecorder, NullRecorder
from src.pipeline.resumable import Stage, run_stages
from src.vector import Embedder, VectorStore

settings = get_settings()


def normalize_url(url: str) -> str:
    """Normalize a URL for stable content hashing.

    Strips tracking params, normalizes scheme/host, removes trailing slashes,
    and sorts query parameters for consistent hashing.
    """
    parsed = urlparse(url.strip())

    # Normalize scheme and host
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower().rstrip(".")

    # Remove www. prefix for consistency
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Normalize path: collapse double slashes, remove trailing slash
    path = re.sub(r"/+", "/", parsed.path)
    if path == "/":
        path = ""
    else:
        path = path.rstrip("/")

    # Remove common tracking query params
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid",
    }
    qs = parse_qs(parsed.query, keep_blank_values=False)
    filtered_qs = {k: v for k, v in qs.items() if k.lower() not in TRACKING_PARAMS}
    sorted_query = urlencode(sorted(filtered_qs.items()), doseq=True)

    normalized = urlunparse((scheme, netloc, path, parsed.params, sorted_query, ""))
    return normalized


def content_hash(url: str) -> str:
    """Deterministic SHA-256 hash of a normalized URL.

    Two URLs that resolve to the same content produce the same hash,
    enabling idempotent processing without re-running expensive stages.
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class PipelineResult:
    success: bool
    url: str
    processing_result: ProcessingResult | None = None
    markdown_path: str | None = None
    json_path: str | None = None
    graph_stats: dict[str, Any] | None = None
    error: str | None = None


# ─── Stage Definitions ────────────────────────────────────────────────────────

async def _stage_extract(ctx: dict[str, Any]) -> dict[str, Any]:
    """Extract content from URL."""
    extractor: ContentExtractor = ctx["extractor"]
    url: str = ctx["url"]
    extracted = await extractor.extract(url)
    return {"extracted": extracted}


async def _stage_chunk(ctx: dict[str, Any]) -> dict[str, Any]:
    """Chunk extracted content into semantic pieces."""
    chunker: SemanticChunker = ctx["chunker"]
    extracted: ExtractedContent = ctx["extracted"]
    chunks = chunker.chunk(extracted.raw_text, extracted.title)
    for chunk in chunks:
        chunk.metadata["source_url"] = ctx["url"]
    return {"chunks": chunks}


async def _stage_embed(ctx: dict[str, Any]) -> dict[str, Any]:
    """Embed chunks and upsert into vector store."""
    embedder: Embedder = ctx["embedder"]
    vector_store: VectorStore = ctx["vector_store"]
    chunks: list[DocumentChunk] = ctx["chunks"]
    url: str = ctx["url"]

    chunks = await embedder.embed_chunks(chunks)
    vector_store.upsert_chunks(chunks, url)
    return {"chunks": chunks}


def deduplicate_entities(
    entities: list[EnrichedEntity],
) -> list[EnrichedEntity]:
    """Deduplicate entities by normalized name, keeping highest confidence.

    Mirrors the EntityResolver's ``normalize_name`` rules so "VS Code" and
    "vscode" collapse to the same key within a single source.
    """
    seen: dict[str, EnrichedEntity] = {}
    for entity in entities:
        key = normalize_name(entity.name)
        if key not in seen or entity.confidence > seen[key].confidence:
            seen[key] = entity
    return list(seen.values())


async def _stage_enrich(ctx: dict[str, Any]) -> dict[str, Any]:
    """Enrich with entity detection, web search, and relationship extraction."""
    enrichment: EnrichmentPipeline = ctx["enrichment"]
    chunks: list[DocumentChunk] = ctx["chunks"]
    entities, relationships, steps = await enrichment.enrich(chunks)

    # Deduplicate entities
    entities = deduplicate_entities(entities)

    return {"entities": entities, "relationships": relationships, "steps": steps}


async def _stage_categorize(ctx: dict[str, Any]) -> dict[str, Any]:
    """Categorize entities into topics."""
    categorizer: Categorizer = ctx["categorizer"]
    entities: list[EnrichedEntity] = ctx["entities"]
    extracted: ExtractedContent = ctx["extracted"]

    categorized = await categorizer.categorize(entities)

    # Handle carousel images if applicable
    carousel_data = None
    if extracted.content_type and extracted.content_type.value == "carousel":
        carousel_data = await categorizer.categorize_carousel_images(extracted.raw_text)

    return {"categorized": categorized, "carousel_data": carousel_data}


async def _stage_format(ctx: dict[str, Any]) -> dict[str, Any]:
    """Generate markdown and JSON output files."""
    categorized: list[CategorizedItem] = ctx["categorized"]
    url: str = ctx["url"]
    steps: list[str] = ctx.get("steps", [])
    carousel_data = ctx.get("carousel_data")

    md_path, json_path = generate_outputs(
        categorized, url, settings.OUTPUT_DIR,
        steps=steps, carousel_data=carousel_data,
    )
    return {"md_path": str(md_path), "json_path": str(json_path)}


async def _stage_graph_update(ctx: dict[str, Any]) -> dict[str, Any]:
    """Update the knowledge graph.

    Two modes:
    - Outbox mode (a CRUD session is present): PostgreSQL is the source of
      truth. We do NOT write Neo4j/Qdrant directly here — the persistence +
      projection happens via the transactional outbox (see persist_and_publish
      in src.pipeline.outbox). Returns a note instead of graph write stats.
    - Standalone mode (no session, e.g. CLI): writes Neo4j directly, as before.
    """
    categorized: list[CategorizedItem] = ctx["categorized"]
    if ctx.get("db") is not None:
        logger.info("graph_update: projections deferred to outbox worker")
        return {
            "graph_stats": {
                "outbox": True,
                "entities_pending": len(categorized),
                "relationships_pending": len(ctx.get("relationships", [])),
            }
        }

    graph_store: Neo4jGraphStore = ctx["graph_store"]
    relationships: list[ExtractedRelationship] = ctx.get("relationships", [])

    merge_result = await graph_store.upsert_knowledge(categorized, relationships=relationships)
    return {"graph_stats": merge_result.__dict__ if merge_result else {}}


# Ordered pipeline stages
PIPELINE_STAGES: list[Stage] = [
    Stage(name="extract", order=1, fn=_stage_extract),
    Stage(name="chunk", order=2, fn=_stage_chunk),
    Stage(name="embed", order=3, fn=_stage_embed),
    Stage(name="enrich", order=4, fn=_stage_enrich),
    Stage(name="categorize", order=5, fn=_stage_categorize),
    Stage(name="format", order=6, fn=_stage_format),
    Stage(name="graph_update", order=7, fn=_stage_graph_update),
]

STAGE_NAMES: list[str] = [s.name for s in PIPELINE_STAGES]


class KnowledgeGraphPipeline:
    """Main pipeline orchestrating all stages with checkpoint/resume."""

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
        self.graph_store = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        logger.info("Initializing Neo4j graph store...")
        self.graph_store = await create_graph_store()
        self.graph_store.set_embedder(self.embedder)
        self._initialized = True
        logger.success("Neo4j graph store initialized")

    async def close(self):
        await self.extractor.close()
        await self.enrichment.close()
        if self.embedder.openai_client:
            await self.embedder.openai_client.close()
        await self.categorizer.close()

    async def process_url(
        self,
        url: str,
        recorder: BaseRecorder | None = None,
        force: bool = False,
        db=None,
    ) -> PipelineResult:
        """Process a single URL through all pipeline stages.

        Args:
            url: The URL to process.
            recorder: Checkpoint recorder. Uses NullRecorder if None.
            force: If True, reprocess even if already completed.
            db: Optional CRUDOperations session. When provided, Neo4j/Qdrant
                projections are deferred to the transactional outbox and PG is
                treated as the source of truth.
        """
        start_time = time.time()
        logger.info(f"Starting pipeline for: {url}")
        rec = recorder or NullRecorder()

        base_context: dict[str, Any] = {
            "url": url,
            "extractor": self.extractor,
            "chunker": self.chunker,
            "embedder": self.embedder,
            "vector_store": self.vector_store,
            "enrichment": self.enrichment,
            "categorizer": self.categorizer,
            "graph_store": self.graph_store,
            "db": db,
        }

        result = await run_stages(PIPELINE_STAGES, rec, initial_context=base_context)

        processing_time = int((time.time() - start_time) * 1000)

        if not result.success:
            logger.error(f"Pipeline failed at stage '{result.failed_stage}': {result.error}")
            return PipelineResult(
                success=False,
                url=url,
                error=result.error,
            )

        # Build ProcessingResult from final context
        ctx = result.context
        processing_result = ProcessingResult(
            url=url,
            success=True,
            extracted_content=ctx.get("extracted"),
            chunks=ctx.get("chunks", []),
            entities=ctx.get("entities", []),
            categorized_items=ctx.get("categorized", []),
            relationships=ctx.get("relationships", []),
            steps=ctx.get("steps", []),
            processing_time_ms=processing_time,
            stages_completed=result.completed_stages,
        )

        logger.success(
            f"Pipeline completed in {processing_time}ms: "
            f"{len(ctx.get('entities', []))} entities, "
            f"{len(ctx.get('categorized', []))} categorized"
        )

        return PipelineResult(
            success=True,
            url=url,
            processing_result=processing_result,
            markdown_path=ctx.get("md_path"),
            json_path=ctx.get("json_path"),
            graph_stats=ctx.get("graph_stats"),
        )

    async def process_batch(
        self, urls: list[str], max_concurrent: int = None
    ) -> list[PipelineResult]:
        max_concurrent = max_concurrent or settings.MAX_CONCURRENT_URLS
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(url: str) -> PipelineResult:
            async with semaphore:
                return await self.process_url(url)

        tasks = [process_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                final_results.append(PipelineResult(success=False, url=url, error=str(result)))
            else:
                final_results.append(result)
        return final_results


async def main():
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
                print("\nSuccess!")
                print(f"   Markdown: {result.markdown_path}")
                print(f"   JSON: {result.json_path}")
            else:
                print(f"\nFailed: {result.error}")
        else:
            results = await pipeline.process_batch(urls)
            print(f"\nBatch Results ({len(results)} URLs):")
            for r in results:
                status = "OK" if r.success else "FAIL"
                print(f"  [{status}] {r.url}")
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
