import asyncio
import json
import re
from pathlib import Path

from loguru import logger

from src.config import get_settings
from src.config.models import (
    CategorizedItem,
    ContentType,
    EnrichedEntity,
    ExtractedRelationship,
    TopicCategory,
)
from src.enrichment import LLMClient

settings = get_settings()

# Path to taxonomy config
TAXONOMY_PATH = Path(__file__).parent.parent.parent / "config" / "taxonomy.json"


def _load_taxonomy() -> tuple[dict, dict]:
    """Load taxonomy from config file, falling back to defaults."""
    if TAXONOMY_PATH.exists():
        try:
            with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Convert to enum-keyed dicts
            topic_taxonomy = {}
            for topic_key, topic_data in data.get("topics", {}).items():
                try:
                    enum_key = TopicCategory(topic_key)
                    topic_taxonomy[enum_key] = topic_data.get("subtopics", [])
                except ValueError:
                    logger.warning(f"Unknown topic category: {topic_key}")
            
            content_types = {}
            for ct_key, ct_desc in data.get("content_types", {}).items():
                try:
                    enum_key = ContentType(ct_key)
                    content_types[enum_key] = ct_desc
                except ValueError:
                    logger.warning(f"Unknown content type: {ct_key}")
            
            return topic_taxonomy, content_types
        except Exception as e:
            logger.warning(f"Failed to load taxonomy from {TAXONOMY_PATH}: {e}")
    
    # Fallback to hardcoded defaults
    return _default_topic_taxonomy(), _default_content_types()


def _default_topic_taxonomy() -> dict:
    """Default topic taxonomy."""
    return {
        TopicCategory.FRONTEND: ["react", "vue", "svelte", "angular", "next.js"],
        TopicCategory.BACKEND: ["api-design", "rest", "graphql", "microservices"],
        TopicCategory.DEVOPS: ["ci-cd", "docker", "kubernetes", "monitoring"],
        TopicCategory.AI_ML: ["rag", "embeddings", "llm-agents", "prompt-engineering"],
        TopicCategory.DATABASE: ["postgresql", "mysql", "mongodb", "redis"],
        TopicCategory.SECURITY: ["auth", "oauth", "jwt", "encryption"],
        TopicCategory.TESTING: ["unit-testing", "integration-testing", "e2e-testing"],
        TopicCategory.ARCHITECTURE: ["clean-architecture", "microservices", "design-patterns"],
        TopicCategory.PERFORMANCE: ["optimization", "caching", "profiling"],
        TopicCategory.MOBILE: ["react-native", "flutter", "expo"],
        TopicCategory.CLOUD: ["aws", "gcp", "azure", "serverless"],
        TopicCategory.OTHER: ["uncategorized"],
    }


def _default_content_types() -> dict:
    """Default content type definitions."""
    return {
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


# Load at module level
TOPIC_TAXONOMY, CONTENT_TYPE_DEFINITIONS = _load_taxonomy()


class Categorizer:
    def __init__(self):
        self.llm = LLMClient()
        self.model = None  # Let LLMClient use configured provider's model

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

        prompt = f"""Analyze the following tech content deeply and return a JSON object
with ALL of these fields:

1. "topic": ONE of [{", ".join(topics)}]
2. "topic_confidence": float 0.0-1.0
3. "subtopics": array of 1-3 strings from the subtopics list matching the chosen topic
4. "content_type": ONE of the content types below
5. "type_confidence": float 0.0-1.0
6. "summary": 2-3 sentence summary describing WHAT the content covers based ONLY on the source content.
   Do NOT invent information not in the source. If the source shows Maya rigs, say "The content shows Maya rigs".
7. "key_points": array of 3-7 key points. Each point should be something explicitly mentioned in the source.
   Include specific names, tools, or websites visible in the source.
8. "detailed_analysis": 2-3 paragraphs analyzing the content's approach based ONLY on what the source shows.

Content type definitions:
{content_type_defs}

Available subtopics per topic:
{json.dumps(all_subtopics, indent=2)}

Content to analyze:
{text}

CRITICAL RULES:
- ONLY describe what is EXPLICITLY in the source content
- Do NOT hallucinate or infer information not present
- If the source shows a video about Maya 3D rigs, describe it as "Maya 3D animation software" NOT "React application"
- Key points must be things actually mentioned or shown in the source

Example response format:
{{
  "topic": "other",
  "topic_confidence": 0.9,
  "subtopics": [],
  "content_type": "tool_review",
  "type_confidence": 0.85,
  "summary": "The content showcases Maya rigs from Agora Studio, including Gamma and Alpha characters. Various rigs are displayed on Gumroad.com for animators.",
  "key_points": [
    "Shows Gamma character from Agora Original Rigs family",
    "Displays Maya rigs available on Gumroad.com",
    "Features Sheriff Rig, Spider Silk, and BreinerRigger"
  ],
  "detailed_analysis": "This content is a showcase of Maya 3D animation rigs. The video displays characters from Agora Studio's Original Rigs family..."
}}

Return ONLY valid JSON."""

        result = await self.llm.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a technical content analyst. CRITICAL RULE: "
                        "You MUST ONLY describe what is explicitly stated in the Source Content. "
                        "Do NOT invent, hallucinate, or assume information that is NOT in the source. "
                        "The summary must be a faithful summary of what the source actually says. "
                        "Key points must be things explicitly mentioned in the source. "
                        "Return valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
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
        source_content = entity.source_text[:800] if entity.source_text else ""
        # For short content, use more of the description
        desc_preview = entity.description[:400] if len(entity.description) > 200 else entity.description
        return (
            f"Name: {entity.name}\n"
            f"Type: {entity.type.value}\n"
            f"Source Content: {source_content}\n"
            f"Description: {desc_preview}\n"
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
            "microservices", "serverless", "ci/cd", "devops", "gitops",
            "rag", "embeddings", "llm", "fine-tuning", "prompt-engineering",
            "jwt", "oauth", "tdd", "bdd", "agile", "scrum",
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
