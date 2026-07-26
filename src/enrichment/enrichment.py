import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from duckduckgo_search import DDGS
from loguru import logger

from src.config import get_settings
from src.config.models import DocumentChunk, EnrichedEntity, EntityType
from src.enrichment.llm_client import LLMClient

settings = get_settings()

# Path to entity config file
ENTITY_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "entities.json"


def _load_entity_config() -> dict:
    """Load entity configuration from JSON file."""
    if ENTITY_CONFIG_PATH.exists():
        try:
            with open(ENTITY_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load entity config: {e}")
    return {}


# Load config at module level
_entity_config = _load_entity_config()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str


class EntityDetector:
    """Detect web/app/tool mentions in text."""

    def __init__(self):
        """Initialize with config file or fallback to defaults."""
        config = _entity_config

        # Load patterns from config
        if config and "entity_patterns" in config:
            self.ENTITY_PATTERNS = {}
            for type_name, entities in config["entity_patterns"].items():
                # Convert entity list to regex pattern
                escaped = [re.escape(e) for e in entities]
                pattern = r"\b(" + "|".join(escaped) + r")\b"
                # Map config type name to EntityType enum
                try:
                    entity_type = EntityType(type_name)
                except ValueError:
                    entity_type = EntityType.UNKNOWN
                self.ENTITY_PATTERNS[entity_type] = [pattern]
            logger.info(
                f"Loaded {sum(len(v) for v in config['entity_patterns'].values())} "
                f"entities from config"
            )
        else:
            # Fallback to hardcoded patterns
            self.ENTITY_PATTERNS = self._get_default_patterns()

        # Load known entities from config
        if config and "known_entities" in config:
            self.KNOWN_ENTITIES = set(config["known_entities"])
        else:
            self.KNOWN_ENTITIES = self._get_default_known_entities()

        # Load blacklist from config
        if config and "blacklist_words" in config:
            self.BLACKLIST_WORDS = frozenset(config["blacklist_words"])
        else:
            self.BLACKLIST_WORDS = self._get_default_blacklist()

        # Load min length from config
        if config and "min_entity_length" in config:
            self.MIN_ENTITY_LENGTH = config["min_entity_length"]
        else:
            self.MIN_ENTITY_LENGTH = 3

        # Build word-boundary regex for known entities
        self._KNOWN_ENTITY_PATTERN = re.compile(
            r"\b(" + "|".join(
                re.escape(e) for e in sorted(self.KNOWN_ENTITIES, key=len, reverse=True)
            ) + r")\b",
            re.IGNORECASE,
        )

    def _get_default_patterns(self) -> dict:
        """Return default hardcoded patterns."""
        return {
            EntityType.FRAMEWORK: [
                r"\b(react|vue|svelte|angular|next\.js|nuxt|astro|remix|solid|qwik)\b",
                r"\b(django|fastapi|flask|express|nest\.js|spring|laravel|rails)\b",
                r"\b(tailwind|bootstrap|material-ui|chakra|shadcn|radix)\b",
            ],
            EntityType.LIBRARY: [
                r"\b(prisma|drizzle|sqlalchemy|typeorm|mongoose|drizzle-orm)\b",
                r"\b(lodash|axios|react-query|swr|zustand|redux|jotai|recoil)\b",
                r"\b(jest|vitest|playwright|cypress|pytest)\b",
            ],
            EntityType.PLATFORM: [
                r"\b(aws|gcp|azure|vercel|netlify|railway|render|fly\.io|cloudflare)\b",
                r"\b(kubernetes|k8s|docker|terraform|ansible)\b",
            ],
            EntityType.SERVICE: [
                r"\b(stripe|auth0|clerk|supabase|firebase|planetscale|neon)\b",
                r"\b(github|gitlab|bitbucket)\b",
            ],
            EntityType.DATABASE: [
                r"\b(postgres|mysql|mongodb|redis|sqlite|planetscale|neon)\b",
            ],
            EntityType.TOOL: [
                r"\b(vscode|intellij|vim|neovim|cursor|windsurf|zed)\b",
                r"\b(github copilot|claude|chatgpt|gemini)\b",
            ],
            EntityType.WEB_APP: [
                r"\b(saas|dashboard|admin panel|web app)\b",
            ],
            EntityType.MOBILE_APP: [
                r"\b(react native|expo|flutter|ios|android|swift|kotlin)\b",
            ],
            EntityType.LANGUAGE: [
                r"\b(typescript|javascript|python|rust|golang|java)\b",
            ],
            EntityType.API: [
                r"\b(rest api|graphql|grpc|webhook)\b",
            ],
            EntityType.CREATIVE_SOFTWARE: [
                r"\b(blender|unity|unreal|unreal engine|maya|cinema 4d|c4d|3ds max)\b",
                r"\b(houdini|zbrush|mudbox|substance painter|substance designer)\b",
                r"\b(after effects|premiere pro|final cut|davinci resolve|motion)\b",
                r"\b(photoshop|illustrator|indesign|figma|sketch|affinity)\b",
                r"\b(d5 render|vray|corona|octane|redshift|arnold)\b",
            ],
        }

    def _get_default_known_entities(self) -> set:
        """Return default known entities."""
        return {
            "react", "vue", "svelte", "angular", "next.js", "nuxt", "astro", "remix",
            "django", "fastapi", "flask", "express", "nest.js", "spring", "laravel",
            "tailwind", "bootstrap", "material-ui", "chakra", "shadcn", "radix",
            "prisma", "drizzle", "sqlalchemy", "typeorm", "mongoose",
            "postgresql", "mysql", "mongodb", "redis", "sqlite", "planetscale", "neon",
            "aws", "gcp", "azure", "vercel", "netlify", "railway", "render", "fly.io",
            "kubernetes", "docker", "terraform", "ansible",
            "stripe", "auth0", "clerk", "supabase", "firebase",
            "github", "gitlab", "bitbucket",
            "vscode", "intellij", "vim", "neovim", "cursor", "windsurf",
            "jest", "vitest", "playwright", "cypress", "pytest",
            "react native", "expo", "flutter",
            "typescript", "javascript", "python", "rust", "java", "kotlin",
            "blender", "unity", "unreal", "unreal engine", "maya", "cinema 4d", "c4d",
            "3ds max", "houdini", "zbrush", "mudbox", "substance painter",
            "substance designer", "after effects", "premiere pro", "final cut",
            "davinci resolve", "photoshop", "illustrator", "figma", "sketch",
            "d5 render", "vray", "corona", "octane", "redshift", "arnold",
        }

    def _get_default_blacklist(self) -> frozenset:
        """Return default blacklist words."""
        return frozenset({
            "follow", "followed", "following", "follows",
            "like", "liked", "likes", "liking",
            "comment", "commented", "comments",
            "share", "shared", "shares", "sharing",
            "save", "saved", "saves", "saving",
            "view", "views", "viewing",
            "post", "posted", "posts", "posting",
            "reel", "reels", "story", "stories",
            "feed", "feeds", "explore", "discover",
            "tag", "tags", "tagged", "hashtag",
            "mention", "mentions", "mentioned",
            "dm", "dms", "inbox", "message", "messages",
            "profile", "bio", "username", "account",
            "notifications", "notification", "alert", "alerts",
            "search", "filter", "filters",
            "subscribe", "subscriber", "subscribers", "subscription",
            "trending", "viral", "popular",
            "first", "second", "third", "last", "next", "prev",
            "new", "old", "best", "top", "good", "bad", "great",
            "more", "less", "many", "few", "some", "all",
            "this", "that", "these", "those", "what", "which",
            "who", "how", "when", "where", "why",
            "can", "could", "would", "should", "will",
            "make", "made", "making", "do", "done", "doing",
            "get", "got", "getting", "give", "given", "giving",
            "take", "taken", "taking", "put", "putting",
            "see", "seen", "seeing", "look", "looking",
            "go", "going", "went", "gone", "come", "coming",
            "use", "used", "using", "try", "tried", "trying",
            "need", "needed", "want", "wanted", "keep", "kept",
            "let", "set", "run", "ran", "start", "started",
            "check", "checked", "create", "created", "add", "added",
            "find", "found", "tell", "told", "ask", "asked",
            "work", "worked", "working", "call", "called",
            "show", "shown", "showing", "turn", "turned",
            "help", "helped", "helping", "move", "moved",
            "play", "played", "playing", "live", "living",
            "stop", "stopped", "wait", "waiting",
            "think", "thought", "feel", "felt",
            "know", "known", "say", "said",
        })

    def detect(self, text: str, max_entities: int = 20) -> list[dict[str, Any]]:
        """Detect tech entities in text."""
        detected = []
        text_lower = text.lower()

        # Pattern-based detection
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
                for match in matches:
                    matched_text = match.group(0).strip()
                    if not self._is_valid(matched_text):
                        continue
                    context = text[max(0, match.start()-100):match.end()+100]
                    detected.append({
                        "name": matched_text,
                        "type": entity_type,
                        "context": context,
                        "confidence": 0.8,
                    })

        # Boost known entities using word-boundary regex
        for m in self._KNOWN_ENTITY_PATTERN.finditer(text):
            entity_name = m.group(0)
            if not self._is_valid(entity_name):
                continue
            already_detected = any(
                d["name"].lower() == entity_name.lower() for d in detected
            )
            if not already_detected:
                detected.append({
                    "name": entity_name,
                    "type": self._guess_type(entity_name),
                    "context": text[max(0, m.start()-100):m.end()+100],
                    "confidence": 0.9,
                })

        # Deduplicate by name (case-insensitive)
        seen = set()
        unique = []
        for d in detected:
            key = d["name"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(d)

        # Sort by confidence and return top
        unique.sort(key=lambda x: x["confidence"], reverse=True)
        return unique[:max_entities]

    def _is_valid(self, name: str) -> bool:
        """Check if entity name is valid (not too short, not a blacklisted word)."""
        name_lower = name.lower().strip()
        if len(name_lower) < self.MIN_ENTITY_LENGTH:
            return False
        if name_lower in self.BLACKLIST_WORDS:
            return False
        # Skip if it's just common words拼在一起 without meaningful content
        return not all(word in self.BLACKLIST_WORDS for word in name_lower.split())

    def _guess_type(self, name: str) -> EntityType:
        """Guess entity type from name."""
        name_lower = name.lower()

        framework_names = {
            "react", "vue", "svelte", "angular", "next.js",
            "nuxt", "django", "fastapi", "express",
        }
        if name_lower in framework_names:
            return EntityType.FRAMEWORK
        elif name_lower in {"prisma", "drizzle", "lodash", "axios", "zustand", "redux"}:
            return EntityType.LIBRARY
        elif name_lower in {"aws", "gcp", "azure", "vercel", "netlify", "docker", "kubernetes"}:
            return EntityType.PLATFORM
        elif name_lower in {"stripe", "auth0", "supabase", "firebase", "github"}:
            return EntityType.SERVICE
        elif name_lower in {"postgresql", "mysql", "mongodb", "redis"}:
            return EntityType.DATABASE
        elif name_lower in {"vscode", "intellij", "jest", "playwright"}:
            return EntityType.TOOL
        elif name_lower in {"react native", "expo", "flutter"}:
            return EntityType.MOBILE_APP
        elif name_lower in {"typescript", "python", "rust", "go"}:
            return EntityType.LANGUAGE
        elif name_lower in {
            "blender", "unity", "unreal", "maya", "cinema 4d", "houdini",
            "zbrush", "after effects", "premiere pro", "davinci resolve",
            "photoshop", "illustrator", "figma", "d5 render", "vray",
        }:
            return EntityType.CREATIVE_SOFTWARE
        return EntityType.UNKNOWN


class WebSearcher:
    """Search the web for entity information."""

    # Domains to exclude from results
    URL_BLACKLIST = frozenset({
        "google.com", "www.google.com", "accounts.google.com",
        "facebook.com", "www.facebook.com", "m.facebook.com",
        "twitter.com", "www.twitter.com", "x.com",
        "instagram.com", "www.instagram.com",
        "linkedin.com", "www.linkedin.com",
        "reddit.com", "www.reddit.com",
        "youtube.com", "www.youtube.com",
        "tiktok.com", "www.tiktok.com",
        "pinterest.com", "www.pinterest.com",
        "medium.com", "dev.to",
        "quora.com", "www.quora.com",
        "wikipedia.org", "en.wikipedia.org",
    })

    # Title patterns indicating low-value results
    TITLE_BLACKLIST = re.compile(
        r"(sign.?in|log.?in|log.?on|sign.?up|register|create.?account|"
        r"forgot.?password|cookie|privacy|terms.?of|"
        r"sponsored|advertisement|ad\b|"
        r"page.?not.?found|404|error|"
        r"download.?now|install|upgrade|"
        r"privacy.?policy|terms.?and.?conditions)",
        re.IGNORECASE,
    )

    def __init__(self):
        self.ddgs = DDGS()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; InstaGPT-GraphRAG/0.1)"}
        )

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search using DuckDuckGo (runs sync DDGS in thread)."""
        results = []

        try:
            ddgs_results = await asyncio.to_thread(
                self.ddgs.text, query, max_results
            )

            for r in ddgs_results:
                url = r.get("href", "")
                title = r.get("title", "")
                snippet = r.get("body", "")

                # Filter out blacklisted URLs
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.lower().removeprefix("www.")
                if domain in self.URL_BLACKLIST:
                    continue

                # Filter out blacklisted titles
                if self.TITLE_BLACKLIST.search(title):
                    continue

                # Skip empty or very short snippets
                if len(snippet.strip()) < 20:
                    continue

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="duckduckgo"
                ))
        except Exception as e:
            logger.warning(f"DDGS search failed: {e}")

        return results

    async def search_entity(self, entity_name: str, entity_type: EntityType) -> list[SearchResult]:
        """Search for specific entity info with disambiguated queries."""
        # Add disambiguation based on entity type
        type_disambiguation = {
            EntityType.FRAMEWORK: "javascript framework",
            EntityType.LIBRARY: "software library package",
            EntityType.TOOL: "developer tool",
            EntityType.PLATFORM: "cloud platform service",
            EntityType.SERVICE: "web service API",
            EntityType.DATABASE: "database system",
            EntityType.LANGUAGE: "programming language",
            EntityType.MOBILE_APP: "mobile app framework",
        }

        disambiguation = type_disambiguation.get(entity_type, "")
        if disambiguation:
            query = f'"{entity_name}" {disambiguation} features documentation'
        else:
            query = f'"{entity_name}" features documentation'

        return await self.search(query, max_results=8)

    async def find_alternatives(
        self, entity_name: str, entity_type: EntityType
    ) -> list[dict[str, Any]]:
        """Find similar/alternative tools."""
        query = f'"{entity_name}" alternatives competitors similar tools'
        results = await self.search(query, max_results=10)

        alternatives = []
        for r in results:
            # Extract potential alternative names from snippets
            alt_names = self._extract_alternatives(r.snippet, entity_name)
            for alt in alt_names:
                alternatives.append({
                    "name": alt,
                    "description": r.snippet[:200],
                    "url": r.url,
                    "source": r.source
                })

        # Deduplicate
        seen = set()
        unique = []
        for alt in alternatives:
            key = alt["name"].lower()
            if key not in seen and key != entity_name.lower():
                seen.add(key)
                unique.append(alt)

        return unique[:8]

    def _extract_alternatives(self, text: str, exclude: str) -> list[str]:
        """Extract alternative names from text."""
        # Common patterns for alternatives
        patterns = [
            r"(?:alternatives?|competitors?|similar to|like)\s+([A-Z][a-zA-Z0-9\-\.]+)",
            r"(?:vs|versus)\s+([A-Z][a-zA-Z0-9\-\.]+)",
            r"([A-Z][a-zA-Z0-9\-\.]+)\s+(?:vs|versus)",
        ]

        found = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)

        # Expanded stopword list
        stopwords = {
            "the", "and", "or", "but", "for", "with", "from", "this", "that",
            "are", "was", "were", "been", "being", "have", "has", "had", "having",
            "does", "did", "doing", "will", "would", "could", "should", "may",
            "might", "can", "shall", "must", "need", "dare", "ought", "used",
            "to", "of", "in", "on", "at", "by", "for", "with", "about", "against",
            "between", "through", "during", "before", "after", "above", "below",
            "out", "off", "over", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all", "both",
            "each", "few", "more", "most", "other", "some", "such", "no", "nor",
            "not", "only", "own", "same", "so", "than", "too", "very", "just",
            "don", "now", "also", "well", "back", "even", "still", "new", "way",
            "use", "get", "make", "like", "want", "look", "take", "come", "think",
            "see", "know", "give", "first", "good", "find", "tell", "ask", "work",
            "seem", "feel", "try", "leave", "call", "need", "become", "keep",
            "let", "begin", "show", "hear", "play", "run", "move", "live", "believe",
            "bring", "happen", "write", "provide", "sit", "stand", "lose", "pay",
            "meet", "include", "continue", "set", "learn", "change", "lead",
            "understand", "watch", "follow", "stop", "create", "speak", "read",
            "allow", "add", "spend", "grow", "open", "walk", "win", "offer",
            "remember", "love", "consider", "appear", "buy", "wait", "serve",
            "die", "send", "expect", "build", "stay", "fall", "cut", "reach",
            "kill", "remain", "suggest", "raise", "pass", "sell", "require",
            "report", "decide", "pull", "develop", "agree", "support", "hold",
            "produce", "eat", "apply", "安排", "suggest", "recommend", "best",
            "top", "popular", "trending", "new", "latest", "great", "awesome",
        }

        # Filter out common words
        filtered = [f for f in found if len(f) > 2 and f.lower() not in stopwords]

        return list(set(filtered))[:5]

    async def close(self):
        await self.client.aclose()


class EnrichmentPipeline:
    """Main enrichment pipeline combining detection and search."""

    BATCH_SIZE = 15  # max entities per LLM batch call

    def __init__(self):
        self.detector = EntityDetector()
        self.searcher = WebSearcher()
        self.llm = LLMClient()

    async def enrich(self, chunks: list[DocumentChunk]) -> list[EnrichedEntity]:
        """Enrich chunks with web search results and batch LLM descriptions."""
        entity_map = self._detect_entities(chunks)
        if not entity_map:
            return []

        searched = await self._search_entities_concurrent(entity_map)
        descriptions = await self._generate_descriptions_batch(searched)
        return self._assemble_enriched(searched, descriptions)

    def _detect_entities(self, chunks):
        """Phase 1: Detect and deduplicate entities (local, no AI)."""
        all_entities = []
        for chunk in chunks:
            detected = self.detector.detect(chunk.text)
            for det in detected:
                det["source_chunk_id"] = chunk.id
                det["source_text"] = chunk.text  # Full source text for LLM context
            all_entities.extend(detected)

        entity_map = {}
        for det in all_entities:
            key = det["name"].lower()
            if key not in entity_map:
                entity_map[key] = det
                entity_map[key]["source_chunks"] = [det["source_chunk_id"]]
            else:
                entity_map[key]["source_chunks"].append(det["source_chunk_id"])
                entity_map[key]["context"] += " ... " + det["context"]
                # Keep longest source text for best context
                if len(det.get("source_text", "")) > len(entity_map[key].get("source_text", "")):
                    entity_map[key]["source_text"] = det["source_text"]
        return entity_map

    async def _search_entities_concurrent(self, entity_map):
        """Phase 2: Concurrent web search per entity."""
        semaphore = asyncio.Semaphore(5)

        async def _search_one(entity_data: dict) -> dict:
            async with semaphore:
                name = entity_data["name"]
                entity_type = entity_data["type"]
                try:
                    search_results = await self.searcher.search_entity(
                        name, entity_type
                    )
                    alternatives = await self.searcher.find_alternatives(
                        name, entity_type
                    )
                    return {
                        **entity_data,
                        "search_results": search_results,
                        "alternatives": alternatives,
                    }
                except Exception as e:
                    logger.warning(f"Web search failed for {name}: {e}")
                    return {
                        **entity_data,
                        "search_results": [],
                        "alternatives": [],
                    }

        results = await asyncio.gather(
            *[_search_one(ed) for ed in entity_map.values()],
            return_exceptions=True,
        )

        valid = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Entity search failed: {r}")
                continue
            valid.append(r)
        return valid

    def _assemble_enriched(self, entities, descriptions):
        """Phase 4: Assemble EnrichedEntity objects (local, no AI)."""
        enriched = []
        for entity_data, desc in zip(entities, descriptions):
            search_results = entity_data.get("search_results", [])
            alternatives = entity_data.get("alternatives", [])
            source_chunk_id = entity_data["source_chunks"][0]

            web_info = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": r.source,
                }
                for r in search_results
            ]

            similar_tools = [
                {
                    "name": a["name"],
                    "description": a["description"],
                    "url": a["url"],
                }
                for a in alternatives
            ]

            enriched.append(EnrichedEntity(
                name=entity_data["name"],
                type=entity_data["type"],
                description=desc,
                web_info=web_info,
                similar_tools=similar_tools,
                source_chunk_id=source_chunk_id,
                source_url=search_results[0].url if search_results else "",
                source_text=entity_data.get("source_text", ""),
                confidence=entity_data["confidence"],
            ))

        return enriched

    async def _generate_descriptions_batch(self, entities: list[dict]) -> list[str]:
        """Generate descriptions for all entities in one LLM call (batched)."""
        if not entities:
            return []

        # Process in sub-batches to keep prompts manageable
        all_descriptions = []

        for batch_start in range(0, len(entities), self.BATCH_SIZE):
            batch = entities[batch_start:batch_start + self.BATCH_SIZE]
            batch_descs = await self._llm_describe_batch(batch)
            all_descriptions.extend(batch_descs)

        return all_descriptions

    async def _llm_describe_batch(self, batch: list[dict]) -> list[str]:
        """Single LLM call to describe a batch of entities."""
        entity_summaries = []
        for e in batch:
            search_results = e.get("search_results", [])
            search_ctx = "\n".join(
                f"  - {r.title}: {r.snippet[:200]}" for r in search_results[:3]
            )
            # Use full source text for context, not just the match window
            source_text = e.get("source_text", "")[:1000]
            entity_summaries.append(
                f"Name: {e['name']}\n"
                f"Type: {e['type']}\n"
                f"Source Content (full transcript):\n{source_text}\n"
                f"Web:\n{search_ctx}"
            )

        entities_text = "\n\n".join(
            f"[Entity {i+1}]\n{summary}" for i, summary in enumerate(entity_summaries)
        )

        prompt = (
            "Summarize what the SOURCE CONTENT says about each entity. "
            "Include specific steps, actions, and instructions mentioned.\n\n"
            "For example, if the source says 'select X then press Y', "
            "your summary should include those exact steps.\n\n"
            "Do NOT generate generic descriptions. Do NOT add external knowledge. "
            "Use ONLY information from the source.\n\n"
            f"Return a JSON object with a \"descriptions\" array containing "
            f"exactly {len(batch)} strings, in the same order as the entities.\n\n"
            f"Example:\n"
            f'Entity: React\n'
            f'Source: "Use React hooks to manage state with useState"\n'
            f'Description: "Shows how to use React hooks for state management '
            f'using the useState function."\n\n'
            f"Entities:\n{entities_text}\n\n"
            "Return ONLY valid JSON."
        )

        try:
            result = await self.llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a content summarizer. Extract and summarize "
                            "information FROM THE SOURCE ONLY. Include specific "
                            "steps, actions, and instructions. If the source says "
                            "'select X, then press Y', include that. Do NOT add "
                            "external knowledge. Return valid JSON with a "
                            "\"descriptions\" array."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                model=settings.OPENAI_CHAT_MODEL,
                temperature=0.2,
                max_tokens=200 * len(batch),
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
            descriptions = data.get("descriptions", [])

            # Validate count matches batch
            if len(descriptions) == len(batch):
                return descriptions

            # If count mismatch, pad with fallbacks
            logger.warning(
                f"Batch description count mismatch: expected {len(batch)}, got {len(descriptions)}"
            )
            while len(descriptions) < len(batch):
                idx = len(descriptions)
                descriptions.append(
                    f"{batch[idx]['name']} is a "
                    f"{batch[idx]['type']} in the source content."
                )
            return descriptions[:len(batch)]

        except Exception as e:
            logger.warning(f"Batch description LLM call failed: {e}")
            return [
                f"{e['name']} is a {e['type']} mentioned in the source content."
                for e in batch
            ]

    async def close(self):
        await self.searcher.close()
        await self.llm.close()
