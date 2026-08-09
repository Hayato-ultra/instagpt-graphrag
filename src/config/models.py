from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from uuid import uuid4, UUID


class ContentType(str, Enum):
    TUTORIAL = "tutorial"
    BEST_PRACTICE = "best_practice"
    BUG_FIX = "bug_fix"
    TIP = "tip"
    COMPARISON = "comparison"
    ARCHITECTURE_DECISION = "architecture_decision"
    TOOL_REVIEW = "tool_review"
    MIGRATION_GUIDE = "migration_guide"
    DOCUMENTATION = "documentation"
    BLOG_POST = "blog_post"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    WEB_APP = "web_app"
    MOBILE_APP = "mobile_app"
    TOOL = "tool"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    PLATFORM = "platform"
    SERVICE = "service"
    API = "api"
    DATABASE = "database"
    LANGUAGE = "language"
    CREATIVE_SOFTWARE = "creative_software"
    CONCEPT = "concept"
    PATTERN = "pattern"
    TECHNIQUE = "technique"
    UNKNOWN = "unknown"


class TopicCategory(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    DEVOPS = "devops"
    AI_ML = "ai_ml"
    DATABASE = "database"
    SECURITY = "security"
    TESTING = "testing"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    MOBILE = "mobile"
    CLOUD = "cloud"
    OTHER = "other"


class ExtractedContent(BaseModel):
    url: HttpUrl
    title: str
    raw_text: str
    markdown: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_strategy: str = "webfetch"
    content_length: int = 0
    word_count: int = 0


class DocumentChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0
    embedding: Optional[List[float]] = None
    chunk_index: int = 0
    header_path: Optional[str] = None


class EnrichedEntity(BaseModel):
    name: str
    type: EntityType = EntityType.UNKNOWN
    description: str
    web_info: List[Dict[str, Any]] = Field(default_factory=list)
    similar_tools: List[Dict[str, Any]] = Field(default_factory=list)
    source_chunk_id: str
    source_url: str
    source_text: str = ""  # Full source transcript for LLM context
    confidence: float = 0.0
    mentioned_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractedRelationship(BaseModel):
    source: str
    target: str
    relation_type: str
    description: str = ""
    confidence: float = 0.0


class CategorizedItem(BaseModel):
    entity: EnrichedEntity
    primary_topic: TopicCategory = TopicCategory.OTHER
    topic_confidence: float = 0.0
    sub_topics: List[str] = Field(default_factory=list)
    content_type: ContentType = ContentType.UNKNOWN
    type_confidence: float = 0.0
    tags: List[str] = Field(default_factory=list)
    summary: str = ""
    key_points: List[str] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
    categorized_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessingResult(BaseModel):
    url: HttpUrl
    success: bool
    error: Optional[str] = None
    extracted_content: Optional[ExtractedContent] = None
    chunks: List[DocumentChunk] = Field(default_factory=list)
    entities: List[EnrichedEntity] = Field(default_factory=list)
    categorized_items: List[CategorizedItem] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)  # Step-by-step guide
    processing_time_ms: int = 0
    stages_completed: List[str] = Field(default_factory=list)


class PipelineStage(str, Enum):
    INPUT = "input"
    EXTRACT = "extract"
    ENRICH = "enrich"
    CATEGORIZE = "categorize"
    FORMAT = "format"
    MERGE = "merge"
    GRAPH_UPDATE = "graph_update"