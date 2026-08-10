"""InstaGPT GraphRAG - URL to Knowledge Graph Pipeline."""

__version__ = "0.1.0"
__author__ = "InstaGPT"

from src.config import get_settings, Settings
from src.config.models import (
    ExtractedContent,
    DocumentChunk,
    EnrichedEntity,
    CategorizedItem,
    ProcessingResult,
    PipelineStage,
    EntityType,
    ContentType,
    TopicCategory,
    InstagramContentType,
    CarouselImageCategory,
)

# Feature-based imports
from src.extraction import ContentExtractor, SemanticChunker
from src.enrichment import (
    EntityDetector,
    WebSearcher,
    EnrichmentPipeline,
    Categorizer,
    LLMClient,
)
from src.graph import GraphStore, Neo4jGraphStore, create_graph_store
from src.vector import Embedder, VectorStore
from src.pipeline import KnowledgeGraphPipeline, PipelineResult
from src.output import MarkdownGenerator, JSONGenerator, generate_outputs

__all__ = [
    "get_settings",
    "Settings",
    "ExtractedContent",
    "DocumentChunk",
    "EnrichedEntity",
    "CategorizedItem",
    "ProcessingResult",
    "PipelineStage",
    "EntityType",
    "ContentType",
    "TopicCategory",
    "InstagramContentType",
    "CarouselImageCategory",
    # Features
    "ContentExtractor",
    "SemanticChunker",
    "EntityDetector",
    "WebSearcher",
    "EnrichmentPipeline",
    "Categorizer",
    "LLMClient",
    "GraphStore",
    "Neo4jGraphStore",
    "create_graph_store",
    "Embedder",
    "VectorStore",
    "KnowledgeGraphPipeline",
    "PipelineResult",
    "MarkdownGenerator",
    "JSONGenerator",
    "generate_outputs",
]