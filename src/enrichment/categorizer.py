import asyncio
import json
import re

from loguru import logger

from src.config import get_settings
from src.config.models import (
    CategorizedItem,
    ContentType,
    EnrichedEntity,
    TopicCategory,
)
from src.enrichment import LLMClient

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

    async def categorize(self, entities: list[EnrichedEntity]) -> list[CategorizedItem]:
        """Categorize all entities with concurrent LLM calls."""
        if not entities:
            return []

        semaphore = asyncio.Semaphore(5)

        async def _run(entity: EnrichedEntity) -> CategorizedItem:
            async with semaphore:
                return await self._categorize_entity(entity)

        results = await asyncio.gather(*[_run(e) for e in entities], return_exceptions=True)

        categorized = []
        for entity, result in zip(entities, results):
            if isinstance(result, Exception):
                logger.warning(f"Categorization failed for {entity.name}: {result}")
                categorized.append(self._fallback_categorize(entity))
            else:
                categorized.append(result)

        return categorized

    async def _categorize_entity(self, entity: EnrichedEntity) -> CategorizedItem:
        """Categorize a single entity with one LLM call."""
        text = self._prepare_text(entity)
        topics = [t.value for t in TopicCategory]
        content_type_defs = "\n".join(
            f"- {k.value}: {v}" for k, v in CONTENT_TYPE_DEFINITIONS.items()
        )
        all_subtopics = {t.value: subs for t, subs in TOPIC_TAXONOMY.items()}

        prompt = f"""Analyze the following tech content and return a JSON object
with ALL of these fields:

1. "topic": ONE of [{", ".join(topics)}]
2. "topic_confidence": float 0.0-1.0
3. "subtopics": array of 1-3 strings from the subtopics list matching the chosen topic
4. "content_type": ONE of the content types below
5. "type_confidence": float 0.0-1.0
6. "summary": 1-2 sentence summary OF THE SOURCE CONTENT
7. "key_points": array of 3-5 key points FROM THE SOURCE

Content type definitions:
{content_type_defs}

Available subtopics per topic:
{json.dumps(all_subtopics, indent=2)}

Content to analyze:
{text}

IMPORTANT: The summary and key_points must come FROM THE SOURCE CONTENT.
If the source says "select X then press Y", include that in key_points.

Example response format:
{{
  "topic": "creative_software",
  "topic_confidence": 0.9,
  "subtopics": ["3d-modeling"],
  "content_type": "tutorial",
  "type_confidence": 0.85,
  "summary": "Video shows how to create custom axes in Blender.",
  "key_points": ["Select Transform Orientations > Local", "Press + to create axis"]
}}

Return ONLY valid JSON."""

        result = await self.llm.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a content analyzer. Extract and summarize "
                        "information FROM THE SOURCE ONLY. The summary should "
                        "describe what the content says, not what the entity is. "
                        "Key points should be specific steps, actions, or "
                        "instructions from the source. Return valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=self.model,
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = result["content"].strip()

        # Try to extract JSON from response (handle markdown code blocks)
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        elif not content.startswith("{"):
            # Try to find JSON object in response
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start != -1 and brace_end != -1:
                content = content[brace_start:brace_end + 1]

        data = json.loads(content)

        # Parse topic
        topic_str = data.get("topic", "other")
        topic_confidence = float(data.get("topic_confidence", 0.5))
        try:
            primary_topic = TopicCategory(topic_str)
        except ValueError:
            primary_topic = TopicCategory.OTHER

        # Parse subtopics — validate against taxonomy for the chosen topic
        raw_subtopics = data.get("subtopics", [])
        valid_subtopics = TOPIC_TAXONOMY.get(primary_topic, [])
        sub_topics = [s for s in raw_subtopics if s in valid_subtopics][:3]

        # Parse content type
        type_str = data.get("content_type", "unknown")
        type_confidence = float(data.get("type_confidence", 0.5))
        try:
            content_type = ContentType(type_str)
        except ValueError:
            content_type = ContentType.UNKNOWN

        # Parse summary and key points
        summary = data.get("summary", "").strip() or entity.description[:200]
        key_points = data.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = []

        # Tags — local, no LLM call
        tags = self._extract_tags(entity, primary_topic, sub_topics)

        return CategorizedItem(
            entity=entity,
            primary_topic=primary_topic,
            topic_confidence=topic_confidence,
            sub_topics=sub_topics,
            content_type=content_type,
            type_confidence=type_confidence,
            tags=tags,
            summary=summary,
            key_points=key_points,
        )

    def _prepare_text(self, entity: EnrichedEntity) -> str:
        """Prepare text for classification."""
        web_snippets = " ".join(w.get("snippet", "") for w in entity.web_info[:5])
        # Use source_text if available, otherwise fall back to description
        source_content = entity.source_text[:500] if entity.source_text else ""
        return (
            f"Name: {entity.name}\n"
            f"Type: {entity.type.value}\n"
            f"Source Content: {source_content}\n"
            f"Description: {entity.description}\n"
            f"Web: {web_snippets}"
        )

    def _extract_tags(
        self,
        entity: EnrichedEntity,
        primary_topic: TopicCategory,
        sub_topics: list[str],
    ) -> list[str]:
        """Extract relevant tags (local, no LLM call)."""
        tags = [primary_topic.value]
        tags.extend(sub_topics)
        tags.append(entity.type.value)

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

        return list(set(tags))

    def _fallback_categorize(self, entity: EnrichedEntity) -> CategorizedItem:
        """Return fallback categorization when LLM call fails."""
        return CategorizedItem(
            entity=entity,
            primary_topic=TopicCategory.OTHER,
            topic_confidence=0.0,
            sub_topics=[],
            content_type=ContentType.UNKNOWN,
            type_confidence=0.0,
            tags=[entity.type.value],
            summary=entity.description[:200],
            key_points=[],
        )

    async def close(self):
        """Close the LLM client."""
        await self.llm.close()
