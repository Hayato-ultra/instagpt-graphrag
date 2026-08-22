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
        """Categorize all entities with batched LLM calls for speed."""
        if not entities:
            return []

        # Batch entities to reduce LLM calls (batch of 5)
        BATCH_SIZE = 5
        categorized = []

        for i in range(0, len(entities), BATCH_SIZE):
            batch = entities[i:i+BATCH_SIZE]
            batch_results = await self._categorize_batch(batch)
            categorized.extend(batch_results)

        return categorized

    async def _categorize_batch(self, entities: list[EnrichedEntity]) -> list[CategorizedItem]:
        """Categorize a batch of entities in a single LLM call."""
        if len(entities) == 1:
            return [await self._categorize_entity(entities[0])]

        topics = [t.value for t in TopicCategory]
        content_type_defs = "\n".join(
            f"- {k.value}: {v}" for k, v in CONTENT_TYPE_DEFINITIONS.items()
        )

        entities_text = ""
        for i, entity in enumerate(entities):
            text = self._prepare_text(entity)
            entities_text += f"\n[Entity {i+1}] {entity.name} ({entity.type.value})\n{text[:1000]}\n"

        prompt = f"""Analyze these {len(entities)} entities from tutorial/reel content.
For EACH entity, return a JSON object with these fields:

1. "topic": ONE of [{", ".join(topics)}]
2. "topic_confidence": float 0.0-1.0
3. "subtopics": array of 1-3 strings
4. "content_type": ONE of the content types below
5. "type_confidence": float 0.0-1.0
6. "summary": 2-3 sentences describing what PROBLEM this entity solves and what SOLUTION it provides
7. "key_points": array of 3-5 key points describing specific STEPS, COMMANDS, or FEATURES

Content type definitions:
{content_type_defs}

Topic category definitions:
- frontend: UI libraries, CSS frameworks, React/Vue/Angular, component libraries (e.g. tailwind, shadcn, radix), animations, UI/UX tools
- backend: APIs, servers, server frameworks (e.g. express, fastapi, django)
- devops: CI/CD, Docker, Kubernetes, deployment, monitoring
- ai_ml: LLMs, embeddings, RAG, prompt engineering, AI agents
- database: SQL/NoSQL databases, ORMs, data modeling
- security: auth, OAuth, JWT, encryption
- testing: unit/integration/e2e testing frameworks
- architecture: design patterns, system design, clean code
- performance: optimization, caching, profiling
- mobile: React Native, Flutter, Expo
- cloud: AWS/GCP/Azure, serverless, Vercel/Netlify
- other: only if nothing above fits at all

Entities to analyze:
{entities_text}

RULES:
- Focus on WHAT EACH ENTITY DOES IN THIS CONTENT
- Describe the PROBLEM → SOLUTION flow for each
- Include specific commands, tools, and features mentioned
- Key points should be actionable steps or insights
- Return a JSON object with "results" array containing {len(entities)} objects, one per entity

Return ONLY valid JSON."""

        result = await self.llm.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are analyzing tutorial/reel content to understand each entity's PURPOSE and SOLUTION. "
                        "For each entity, describe: What problem does it solve? What steps are shown? "
                        "What tools are used? Return valid JSON with results array."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500 * len(entities),
            response_format={"type": "json_object"},
        )

        content = result["content"].strip()
        logger.debug(f"Categorize batch raw response: {content[:500]}")

        # Parse JSON
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        elif not content.startswith("{"):
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start != -1 and brace_end != -1:
                content = content[brace_start:brace_end + 1]

        try:
            data = json.loads(content)
            results = data.get("results", [])

            categorized = []
            for i, entity in enumerate(entities):
                if i < len(results):
                    r = results[i]
                    # Parse topic
                    topic_str = r.get("topic", "other")
                    try:
                        primary_topic = TopicCategory(topic_str)
                    except ValueError:
                        primary_topic = TopicCategory.OTHER

                    # Parse content type
                    type_str = r.get("content_type", "tutorial")
                    try:
                        content_type = ContentType(type_str)
                    except ValueError:
                        content_type = ContentType.TUTORIAL

                    # Extract tags
                    sub_topics = r.get("subtopics", [])
                    tags = self._extract_tags(entity, primary_topic, sub_topics)

                    categorized.append(CategorizedItem(
                        entity=entity,
                        primary_topic=primary_topic,
                        topic_confidence=float(r.get("topic_confidence", 0.7)),
                        content_type=content_type,
                        type_confidence=float(r.get("type_confidence", 0.7)),
                        summary=r.get("summary", ""),
                        key_points=r.get("key_points", []),
                        sub_topics=sub_topics,
                        tags=tags,
                    ))
                else:
                    categorized.append(self._fallback_categorize(entity))

            return categorized

        except Exception as e:
            logger.warning(f"Batch categorization failed: {e}")
            return [self._fallback_categorize(e) for e in entities]

    async def _categorize_entity(self, entity: EnrichedEntity) -> CategorizedItem:
        """Categorize a single entity with one LLM call."""
        text = self._prepare_text(entity)
        topics = [t.value for t in TopicCategory]
        content_type_defs = "\n".join(
            f"- {k.value}: {v}" for k, v in CONTENT_TYPE_DEFINITIONS.items()
        )
        all_subtopics = {t.value: subs for t, subs in TOPIC_TAXONOMY.items()}

        prompt = f"""Analyze this tutorial/reel content and return a JSON object with these fields:

1. "topic": ONE of [{", ".join(topics)}]
2. "topic_confidence": float 0.0-1.0
3. "subtopics": array of 1-3 strings from the subtopics list
4. "content_type": ONE of the content types below
5. "type_confidence": float 0.0-1.0
6. "summary": 2-3 sentences describing:
   - What PROBLEM does this content solve?
   - What SOLUTION does it provide?
   - What TOOLS/TECHNOLOGIES are used in the solution?
7. "key_points": array of 3-7 key points describing:
   - What specific STEPS are shown
   - What COMMANDS/TOOLS are used
   - What CONFIGURATIONS are made
   - What RESULT is achieved
8. "detailed_analysis": 2-3 paragraphs analyzing the APPROACH and WORKFLOW shown

Content type definitions:
{content_type_defs}

Topic category definitions:
- frontend: UI libraries, CSS frameworks, React/Vue/Angular, component libraries (e.g. tailwind, shadcn, radix), animations, UI/UX tools
- backend: APIs, servers, server frameworks (e.g. express, fastapi, django)
- devops: CI/CD, Docker, Kubernetes, deployment, monitoring
- ai_ml: LLMs, embeddings, RAG, prompt engineering, AI agents
- database: SQL/NoSQL databases, ORMs, data modeling
- security: auth, OAuth, JWT, encryption
- testing: unit/integration/e2e testing frameworks
- architecture: design patterns, system design, clean code
- performance: optimization, caching, profiling
- mobile: React Native, Flutter, Expo
- cloud: AWS/GCP/Azure, serverless, Vercel/Netlify
- other: only if nothing above fits at all

Available subtopics per topic:
{json.dumps(all_subtopics, indent=2)}

Content to analyze:
{text}

RULES:
- Focus on WHAT THE CONTENT TEACHES, not what entities are
- Describe the PROBLEM → SOLUTION flow
- Include specific commands, tools, and configurations mentioned
- Key points should be actionable steps or insights from the content
- Summary should answer: "What will I learn from this content?"

Example response for a React+Vite+Tailwind tutorial:
{{
  "topic": "frontend",
  "topic_confidence": 0.95,
  "subtopics": ["react", "tailwind"],
  "content_type": "tutorial",
  "type_confidence": 0.9,
  "summary": "This tutorial shows how to quickly set up a modern React project using Vite and Tailwind CSS. It solves the problem of boilerplate setup by demonstrating npm create vite, installing Tailwind, and configuring the Vite plugin.",
  "key_points": [
    "Run 'npm create vite' to scaffold React project",
    "Select React framework and JavaScript variant",
    "Install Tailwind CSS via npm",
    "Configure vite.config.js with Tailwind plugin",
    "Start dev server with npm run dev"
  ],
  "detailed_analysis": "The content demonstrates a streamlined approach to setting up a React development environment..."
}}

Return ONLY valid JSON."""

        result = await self.llm.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are analyzing a tutorial/reel to understand its PURPOSE and SOLUTION. "
                        "Focus on: What problem does this solve? What steps are shown? "
                        "What tools are used? What is the workflow? "
                        "Do NOT give generic entity definitions. "
                        "Describe the content's APPROACH and VALUE to the viewer. "
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

    async def categorize_carousel_images(
        self, raw_text: str
    ) -> list[dict]:
        """Categorize each carousel image and map relations between them."""
        carousel_sections = []
        parts = raw_text.split("[Carousel Image ")
        for part in parts[1:]:
            idx_end = part.find("]:")
            if idx_end == -1:
                continue
            image_num = part[:idx_end]
            ocr_text = part[idx_end + 2:].strip()
            carousel_sections.append({"image_num": image_num, "ocr_text": ocr_text})

        if not carousel_sections:
            return []

        # Build context for all images
        images_context = "\n\n".join(
            f"Image {s['image_num']}:\n{s['ocr_text'][:500]}"
            for s in carousel_sections
        )

        try:
            result = await self.llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical content analyst for Instagram carousels. "
                            "Analyze each image's OCR text and categorize it. "
                            "Return valid JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Analyze each carousel image and categorize it.\n\n"
                            "Categories:\n"
                            "- terminal: shows terminal/CLI commands\n"
                            "- code: shows source code\n"
                            "- config: shows configuration file\n"
                            "- ui_result: shows browser/app output\n"
                            "- screenshot: shows a website or app screenshot\n"
                            "- reference: shows documentation or reference material\n"
                            "- other: doesn't fit above categories\n\n"
                            "Also identify:\n"
                            "- Which entities (tools/frameworks) are shown in each image\n"
                            "- How each image relates to the previous one (is it a next step? result?)\n"
                            "- The sequence position of each image\n\n"
                            f"Images:\n{images_context}\n\n"
                            'Return a JSON object with "images" array. Each entry has:\n'
                            "- \"image_number\": string (e.g., \"1\")\n"
                            "- \"category\": one of the categories above\n"
                            "- \"entities\": array of entity names shown\n"
                            "- \"summary\": 1 sentence describing what the image shows\n"
                            "- \"relation_to_previous\": how this relates to the previous image\n"
                            "- \"sequence_position\": integer starting from 1\n\n"
                            "Return ONLY valid JSON."
                        ),
                    },
                ],
                temperature=0.2,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            content = result["content"].strip()

            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            elif not content.startswith("{"):
                brace_start = content.find("{")
                brace_end = content.rfind("}")
                if brace_start != -1 and brace_end != -1:
                    content = content[brace_start:brace_end + 1]

            data = json.loads(content)
            return data.get("images", [])

        except Exception as e:
            logger.warning(f"Carousel image categorization failed: {e}")
            return []

    async def close(self):
        """Close the LLM client."""
        await self.llm.close()
