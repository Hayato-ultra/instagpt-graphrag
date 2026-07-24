import asyncio
from typing import List, Dict, Any, Optional
from collections import defaultdict
import json

from src.config import get_settings
from src.config.models import (
    EnrichedEntity, 
    CategorizedItem, 
    TopicCategory, 
    ContentType,
    DocumentChunk
)
from src.enrichment import LLMClient
from loguru import logger


settings = get_settings()


# Topic taxonomy with subtopics
TOPIC_TAXONOMY = {
    TopicCategory.FRONTEND: [
        "react", "vue", "svelte", "angular", "next.js", "nuxt", "astro", "remix",
        "state-management", "css", "styling", "ui-components", "animations",
        "testing", "performance", "accessibility", "ssr", "ssg", "pwa"
    ],
    TopicCategory.BACKEND: [
        "api-design", "rest", "graphql", "grpc", "microservices", "auth",
        "caching", "database", "orm", "migrations", "background-jobs",
        "message-queues", "websockets", "serverless", "edge-functions"
    ],
    TopicCategory.DEVOPS: [
        "ci-cd", "github-actions", "gitlab-ci", "docker", "kubernetes",
        "terraform", "ansible", "monitoring", "logging", "observability",
        "deployment", "infrastructure", "cloud", "serverless"
    ],
    TopicCategory.AI_ML: [
        "rag", "embeddings", "vector-search", "fine-tuning", "llm-agents",
        "prompt-engineering", "eval", "retrieval", "reranking", "chunking",
        "langchain", "llamaindex", "haystack", "mlops", "model-serving"
    ],
    TopicCategory.DATABASE: [
        "postgresql", "mysql", "mongodb", "redis", "sqlite", "planetscale",
        "prisma", "drizzle", "sqlalchemy", "migrations", "optimization",
        "indexing", "sharding", "replication", "backup"
    ],
    TopicCategory.SECURITY: [
        "auth", "authorization", "oauth", "jwt", "encryption", "https",
        "cors", "csp", "xss", "csrf", "sql-injection", "secrets",
        "vulnerability", "penetration-testing", "compliance"
    ],
    TopicCategory.TESTING: [
        "unit-testing", "integration-testing", "e2e-testing", "playwright",
        "cypress", "jest", "vitest", "pytest", "mocking", "tdd",
        "coverage", "property-testing", "contract-testing"
    ],
    TopicCategory.ARCHITECTURE: [
        "clean-architecture", "ddd", "hexagonal", "microservices", "modular-monolith",
        "event-driven", "cqrs", "event-sourcing", "design-patterns",
        "scalability", "maintainability", "technical-debt"
    ],
    TopicCategory.PERFORMANCE: [
        "optimization", "profiling", "caching", "lazy-loading", "bundle-size",
        "core-web-vitals", "database-optimization", "query-optimization",
        "cdn", "compression", "memory-leaks"
    ],
    TopicCategory.MOBILE: [
        "react-native", "flutter", "expo", "ios", "android", "pwa",
        "capacitor", "native-modules", "offline-first", "push-notifications"
    ],
    TopicCategory.CLOUD: [
        "aws", "gcp", "azure", "serverless", "functions", "containers",
        "managed-services", "cost-optimization", "multi-cloud", "edge"
    ],
}

CONTENT_TYPE_DEFINITIONS = {
    ContentType.TUTORIAL: "Step-by-step guide teaching how to do something",
    ContentType.BEST_PRACTICE: "Recommended patterns and practices",
    ContentType.BUG_FIX: "Solution to a specific bug or issue",
    ContentType.TIP: "Quick useful tip or trick",
    ContentType.COMPARISON: "Comparison between tools/approaches",
    ContentType.ARCHITECTURE_DECISION: "Architectural choice with rationale",
    ContentType.TOOL_REVIEW: "Review or analysis of a tool/service",
    ContentType.MIGRATION_GUIDE: "Guide for migrating between versions/tools",
    ContentType.DOCUMENTATION: "Official or reference documentation",
    ContentType.BLOG_POST: "Article or blog post about a topic",
}


class Categorizer:
    def __init__(self):
        self.llm = LLMClient()
        self.model = settings.OPENAI_CHAT_MODEL
    
    async def categorize(self, entities: List[EnrichedEntity]) -> List[CategorizedItem]:
        """Categorize all entities."""
        categorized = []
        
        for entity in entities:
            item = await self._categorize_entity(entity)
            categorized.append(item)
        
        return categorized
    
    async def _categorize_entity(self, entity: EnrichedEntity) -> CategorizedItem:
        """Categorize a single entity."""
        # Prepare text for classification
        text = self._prepare_text(entity)
        
        # Classify primary topic
        primary_topic, topic_confidence = await self._classify_topic(text)
        
        # Classify sub-topics
        sub_topics = await self._classify_subtopics(text, primary_topic)
        
        # Classify content type
        content_type, type_confidence = await self._classify_content_type(text)
        
        # Extract tags
        tags = await self._extract_tags(entity, primary_topic, sub_topics)
        
        # Generate summary
        summary = await self._generate_summary(entity)
        
        # Extract key points
        key_points = await self._extract_key_points(entity)
        
        return CategorizedItem(
            entity=entity,
            primary_topic=primary_topic,
            topic_confidence=topic_confidence,
            sub_topics=sub_topics,
            content_type=content_type,
            type_confidence=type_confidence,
            tags=tags,
            summary=summary,
            key_points=key_points
        )
    
    def _prepare_text(self, entity: EnrichedEntity) -> str:
        """Prepare text for classification."""
        web_snippets = " ".join(w.get("snippet", "") for w in entity.web_info[:5])
        return f"""
        Name: {entity.name}
        Type: {entity.type.value}
        Description: {entity.description}
        Context: {web_snippets}
        """
    
    async def _classify_topic(self, text: str) -> tuple[TopicCategory, float]:
        """Classify primary topic using LLM."""
        topics = [t.value for t in TopicCategory]
        
        prompt = f"""
        Classify the following tech content into ONE primary topic:
        
        Topics: {", ".join(topics)}
        
        Content:
        {text}
        
        Return JSON: {{"topic": "topic_name", "confidence": 0.0-1.0}}
        """
        
        try:
            result = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": "Classify tech content into topics."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            data = json.loads(result["content"])
            topic_str = data.get("topic", "other")
            confidence = float(data.get("confidence", 0.5))
            
            try:
                topic = TopicCategory(topic_str)
            except ValueError:
                topic = TopicCategory.OTHER
            
            return topic, confidence
        except Exception as e:
            logger.warning(f"Topic classification failed: {e}")
            return TopicCategory.OTHER, 0.5
    
    async def _classify_subtopics(self, text: str, primary_topic: TopicCategory) -> List[str]:
        """Classify sub-topics within primary topic."""
        subtopics = TOPIC_TAXONOMY.get(primary_topic, [])
        if not subtopics:
            return []
        
        prompt = f"""
        From the following sub-topics for "{primary_topic.value}", select 1-3 that best match the content:
        
        Sub-topics: {", ".join(subtopics)}
        
        Content:
        {text}
        
        Return JSON: {{"subtopics": ["sub1", "sub2"]}}
        """
        
        try:
            result = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": "Select relevant sub-topics."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            data = json.loads(result["content"])
            return data.get("subtopics", [])
        except Exception as e:
            logger.warning(f"Sub-topic classification failed: {e}")
            return []
    
    async def _classify_content_type(self, text: str) -> tuple[ContentType, float]:
        """Classify content type."""
        types = [t.value for t in ContentType]
        definitions = "\n".join(f"- {k.value}: {v}" for k, v in CONTENT_TYPE_DEFINITIONS.items())
        
        prompt = f"""
        Classify the content type:
        
        Types and definitions:
        {definitions}
        
        Content:
        {text}
        
        Return JSON: {{"type": "type_name", "confidence": 0.0-1.0}}
        """
        
        try:
            result = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": "Classify content type."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            data = json.loads(result["content"])
            type_str = data.get("type", "unknown")
            confidence = float(data.get("confidence", 0.5))
            
            try:
                ctype = ContentType(type_str)
            except ValueError:
                ctype = ContentType.UNKNOWN
            
            return ctype, confidence
        except Exception as e:
            logger.warning(f"Content type classification failed: {e}")
            return ContentType.UNKNOWN, 0.5
    
    async def _extract_tags(
        self, 
        entity: EnrichedEntity, 
        primary_topic: TopicCategory,
        sub_topics: List[str]
    ) -> List[str]:
        """Extract relevant tags."""
        tags = [primary_topic.value]
        tags.extend(sub_topics)
        tags.append(entity.type.value)
        
        # Add entity-specific tags from name
        name_lower = entity.name.lower()
        tech_keywords = [
            "react", "vue", "svelte", "angular", "nextjs", "nuxt", "astro",
            "django", "fastapi", "flask", "express", "nestjs", "spring",
            "tailwind", "shadcn", "radix", "prisma", "drizzle", "sqlalchemy",
            "postgres", "mysql", "mongodb", "redis", "sqlite",
            "aws", "gcp", "azure", "vercel", "netlify", "railway",
            "kubernetes", "docker", "terraform", "github", "gitlab",
            "openai", "anthropic", "langchain", "llamaindex",
            "jest", "vitest", "playwright", "cypress", "pytest",
        ]
        
        for kw in tech_keywords:
            if kw in name_lower:
                tags.append(kw)
        
        return list(set(tags))  # deduplicate
    
    async def _generate_summary(self, entity: EnrichedEntity) -> str:
        """Generate a concise summary."""
        prompt = f"""
        Write a 1-2 sentence summary of "{entity.name}" ({entity.type.value}):
        {entity.description[:500]}
        
        Key info from web:
        {chr(10).join(f"- {w.get('snippet', '')[:200]}" for w in entity.web_info[:3])}
        
        Be concise and informative.
        """
        
        try:
            result = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": "Write concise technical summaries."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.2,
                max_tokens=100
            )
            return result["content"].strip()
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return entity.description[:200]
    
    async def _extract_key_points(self, entity: EnrichedEntity) -> List[str]:
        """Extract key points from entity info."""
        prompt = f"""
        Extract 3-5 key points about "{entity.name}":
        {entity.description[:500]}
        
        Web info:
        {chr(10).join(f"- {w.get('snippet', '')[:300]}" for w in entity.web_info[:5])}
        
        Return JSON: {{"points": ["point1", "point2", "point3"]}}
        """
        
        try:
            result = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": "Extract key technical points."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            data = json.loads(result["content"])
            return data.get("points", [])
        except Exception as e:
            logger.warning(f"Key points extraction failed: {e}")
            return []
    
    async def close(self):
        """Close the LLM client."""
        await self.llm.close()