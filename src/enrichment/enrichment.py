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
from src.config.models import DocumentChunk, EnrichedEntity, EntityType, ExtractedRelationship
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

        # OCR misread corrections - apply to ALL entity detection
        self._ocr_corrections = {
            "animprops.com": "AnimWorkKes",
            "agora.com": "Agora.com",
            "gumroad.com": "Gumroad.com",
            "ora.com": "Agora.com",
            "animworks.com": "AnimWorkKes",
            "animprops": "AnimWorkKes",
        }
        
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
            EntityType.TOOL: [
                r"\b(opal|stitch|antigravity|mixboard|nano bananas|cloud code)\b",
                r"\b(vscode|intellij|vim|neovim|cursor|windsurf|zed)\b",
                r"\b(github copilot|claude|chatgpt|gemini)\b",
            ],
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
                # Note: github only detected when "repository" or "repo" is mentioned
            ],
            EntityType.DATABASE: [
                r"\b(postgres|mysql|mongodb|redis|sqlite|planetscale|neon)\b",
            ],
            EntityType.WEB_APP: [
                r"\b(saas|dashboard|admin panel|web app)\b",
            ],
            EntityType.MOBILE_APP: [
                r"\b(react native|expo|flutter|ios|android|swift|kotlin)\b",
            ],
            EntityType.LANGUAGE: [],  # Languages are too generic, skip them
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
            EntityType.CONCEPT: [
                r"\b(microservices?|monolith|serverless|edge.?computing|cloud.?native)\b",
                r"\b(ci[\s\/]?cd|continuous.?integration|continuous.?delivery|continuous.?deployment)\b",
                r"\b(devops|gitops|infrastructure.?as.?code|platform.?engineering)\b",
                r"\b(agile|scrum|kanban|sprint|pair.?programming|code.?review)\b",
                r"\b(mvp|pivot|growth.?hacking|product.?market.?fit)\b",
                r"\b(scalability|reliability|availability|observability|monitoring)\b",
                r"\b(api.?first|contract.?first|schema.?first|design.?first)\b",
                r"\b(real.?time|event.?driven|message.?driven|reactive)\b",
            ],
            EntityType.PATTERN: [
                r"\b(design.?pattern|architectural.?pattern|creational.?pattern|structural.?pattern|behavioral.?pattern)\b",
                r"\b(singleton|factory|observer|strategy|decorator|adapter|facade|proxy)\b",
                r"\b(mvc|mvvm|mvp|clean.?architecture|hexagonal|onion|ports.?and.?adapters)\b",
                r"\b(cqrs|event.?sourcing|saga|choreography|orchestration)\b",
                r"\b(repository.?pattern|unit.?of.?work|active.?record|data.?mapper)\b",
                r"\b(circuit.?breaker|bulkhead|retry|timeout|rate.?limiting|backpressure)\b",
                r"\b(lazy.?loading|eager.?loading|pagination|infinite.?scroll|virtual.?scrolling)\b",
                r"\b(throttling|debouncing|memoization|caching|invalidation)\b",
            ],
            EntityType.TECHNIQUE: [
                r"\b(code.?splitting|tree.?shaking|dead.?code.?elimination|minification|bundling)\b",
                r"\b(server.?side.?rendering|static.?site.?generation|incremental.?static.?regeneration)\b",
                r"\b(hydration|partial.?hydration|islands.?architecture|resumability)\b",
                r"\b(dependency.?injection|inversion.?of.?control|service.?locator)\b",
                r"\b(test.?driven.?development|behavior.?driven.?development|property.?based.?testing)\b",
                r"\b(mob.?programming|pair.?programming|trunk.?based.?development|feature.?flags)\b",
                r"\b(blue.?green.?deployment|canary.?deployment|rolling.?deployment|shadow.?deployment)\b",
                r"\b(database.?sharding|read.?replicas|connection.?pooling|query.?optimization)\b",
                r"\b(jwt|oauth|openid.?connect|saml|sso|rbac|abac)\b",
                r"\b(web.?component|shadow.?dom|custom.?element|slot|template)\b",
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
            # Platform names (not useful as entities)
            "instagram", "facebook", "twitter", "youtube", "tiktok",
            "linkedin", "reddit", "pinterest", "snapchat", "discord",
            "medium", "dev.to", "substack", "hashnode",
            # Common filler words from captions
            "actually", "definitely", "really", "just", "also",
            "need", "want", "get", "got", "have", "has",
            # Words that create false entities
            "open", "workforce", "website", "link",
            "anti", "second", "hand",
            "google", "secretly", "launched", "free", "ai", "tools",
            "code", "editor", "cloud",
        })

    def detect(self, text: str, max_entities: int = 40) -> list[dict[str, Any]]:
        """Detect tech entities in text."""
        detected = []
        
        # Strip Instagram hashtags (#word) before entity detection to avoid false positives
        # e.g., "#blender #maya" should not detect "blender" as entity if video is about Maya
        cleaned_text = re.sub(r'#\w+', '', text)
        text_lower = cleaned_text.lower()

        # Pattern-based detection
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
                for match in matches:
                    matched_text = match.group(0).strip()
                    # Apply OCR corrections
                    matched_text = self._ocr_corrections.get(matched_text.lower(), matched_text)
                    if not self._is_valid(matched_text):
                        continue
                    context = text[max(0, match.start()-150):match.end()+150]
                    detected.append({
                        "name": matched_text,
                        "type": entity_type,
                        "context": context,
                        "confidence": 0.8,
                    })

        # Boost known entities using word-boundary regex
        for m in self._KNOWN_ENTITY_PATTERN.finditer(cleaned_text):
            entity_name = m.group(0)
            # Apply OCR corrections
            entity_name = self._ocr_corrections.get(entity_name.lower(), entity_name)
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

        tool_names = {
            "opal", "stitch", "antigravity", "mixboard", "nano bananas", "cloud code",
            "vscode", "intellij", "jest", "playwright",
        }
        if name_lower in tool_names:
            return EntityType.TOOL
        
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
        elif name_lower in {
            "microservices", "monolith", "serverless", "ci/cd", "devops",
            "gitops", "agile", "scrum", "kanban", "observability",
        }:
            return EntityType.CONCEPT
        elif name_lower in {
            "singleton", "factory", "observer", "strategy", "decorator",
            "adapter", "facade", "proxy", "mvc", "mvvm", "cqrs",
            "circuit breaker", "lazy loading", "memoization",
        }:
            return EntityType.PATTERN
        elif name_lower in {
            "code splitting", "tree shaking", "ssr", "sgg", "isr",
            "dependency injection", "tdd", "bdd", "jwt", "oauth",
        }:
            return EntityType.TECHNIQUE
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
            # Run DDGS in thread with timeout
            ddgs_results = await asyncio.wait_for(
                asyncio.to_thread(self.ddgs.text, query, max_results),
                timeout=15.0  # 15 second timeout
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
        except asyncio.TimeoutError:
            logger.warning(f"DDGS search timed out for query: {query[:50]}...")
        except Exception as e:
            logger.warning(f"DDGS search failed: {e}")

        return results

    async def search_entity(self, entity_name: str, entity_type: EntityType) -> list[SearchResult]:
        """Search for specific entity info with disambiguated queries."""
        # Skip search for generic concepts that don't need web search
        # These are too broad and return irrelevant results
        generic_concepts = {
            "web development", "software development", "remote jobs", "freelancing",
            "coding", "programming", "design", "marketing", "writing",
            "ui libraries", "ui components", "animations", "frontend",
            "backend", "full stack", "devops", "cloud computing",
        }
        if entity_name.lower() in generic_concepts:
            logger.debug(f"Skipping search for generic concept: {entity_name}")
            return []
        
        # Skip entities that look like transcription errors (Hindi text, too short, etc.)
        if len(entity_name) < 3:
            return []
        # Skip if contains Hindi/Devanagari characters
        if any('\u0900' <= c <= '\u097F' for c in entity_name):
            return []
        
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
        
        # Special handling for Google AI tools
        google_tools = {
            "opal": "Google Opal AI tool",
            "stitch": "Google Stitch UI design tool",
            "antigravity": "Google Antigravity code editor",
            "mixboard": "Google Mixboard AI tool",
            "nano bananas": "Google Nano Bananas AI tool",
            "cloud code": "Google Cloud Code AI tool",
        }
        
        entity_lower = entity_name.lower()
        if entity_lower in google_tools:
            query = f'{google_tools[entity_lower]} documentation'
        else:
            disambiguation = type_disambiguation.get(entity_type, "")
            # Simplified query to avoid timeouts
            if disambiguation:
                query = f'"{entity_name}" {disambiguation}'
            else:
                query = f'"{entity_name}" software'

        # Use fewer results and shorter timeout
        results = await self.search(query, max_results=5)
        # Filter out irrelevant results (e.g., motorcycle companies for "hero", news sites for "scroll")
        return self._filter_irrelevant_results(results, entity_name)

    def _filter_irrelevant_results(self, results: list, entity_name: str) -> list:
        """Filter out search results that are clearly irrelevant to web development."""
        # Domains that are clearly irrelevant to web development
        irrelevant_domains = {
            # Government/ID
            "uidai.gov.in", "aadhaar",
            # Motorcycles/vehicles
            "heromotocorp.com", "hero.in", "bikewale.com", "bikedekho.com",
            "ktmindia.com", "ktm.com", "bajaj.com", "tvs.com",
            # News/media
            "scroll.in", "scrolller.com", "timesofindia.com", "hindustantimes.com",
            "ndtv.com", "news18.com", "republicworld.com",
            # Encyclopedia
            "wikipedia.org", "britannica.com",
            # Ecommerce
            "amazon.com", "flipkart.com", "ebay.com", "myntra.com", "ajio.com",
            # Social media/messaging
            "facebook.com", "twitter.com", "instagram.com", "whatsapp.com", "wa.me",
            "linkedin.com", "reddit.com", "quora.com",
            # Shopping/product reviews
            "smartprix.com", "91mobiles.com", "gadgets360.com",
            # Dictionary/definition sites
            "merriam-webster.com", "dictionary.com", "cambridge.org",
            # Generic tech news (not documentation)
            "techcrunch.com", "theverge.com", "wired.com",
            # Job boards (not relevant for entity info)
            "naukri.com", "indeed.com", "glassdoor.com",
        }
        
        # Keywords that indicate irrelevant content
        irrelevant_keywords = {
            # Vehicles
            "motorcycle", "bike", "scooter", "vehicle", "automobile", "car",
            "price", "mileage", "on-road", "ex-showroom", "engine",
            # News
            "news", "article", "blog post", "opinion", "editorial",
            # Lifestyle
            "recipe", "cooking", "food", "restaurant",
            "cricket", "football", "sports", "match",
            "movie", "film", "celebrity", "bollywood",
            # Shopping
            "buy", "price", "discount", "offer", "sale",
            # Job related
            "salary", "hiring", "job opening", "interview",
        }
        
        # URL patterns to skip
        irrelevant_url_patterns = [
            "/dictionary/", "/definition/", "/encyclopedia/",
            "/buy/", "/price/", "/shop/",
            "/news/", "/sports/", "/entertainment/",
        ]
        
        filtered = []
        for r in results:
            url_lower = r.url.lower()
            snippet_lower = r.snippet.lower()
            title_lower = r.title.lower()
            
            # Check domain
            is_irrelevant_domain = False
            for domain in irrelevant_domains:
                if domain in url_lower:
                    is_irrelevant_domain = True
                    break
            if is_irrelevant_domain:
                continue
            
            # Check URL patterns
            has_irrelevant_url = False
            for pattern in irrelevant_url_patterns:
                if pattern in url_lower:
                    has_irrelevant_url = True
                    break
            if has_irrelevant_url:
                continue
            
            # Check for irrelevant keywords in title/snippet
            has_irrelevant_keyword = False
            for keyword in irrelevant_keywords:
                if keyword in title_lower or keyword in snippet_lower:
                    has_irrelevant_keyword = True
                    break
            if has_irrelevant_keyword:
                continue
            
            # Check if the result is actually about the entity in a web dev context
            entity_lower = entity_name.lower()
            if entity_lower in title_lower or entity_lower in snippet_lower:
                filtered.append(r)
            # Only keep results that mention the entity (remove the fallback)
        
        return filtered[:5]  # Limit to 5 relevant results

    async def find_alternatives(
        self, entity_name: str, entity_type: EntityType
    ) -> list[dict[str, Any]]:
        """Find similar/alternative tools."""
        # Skip alternative search for Google AI tools (they don't have direct alternatives)
        google_tools = {"opal", "stitch", "antigravity", "mixboard", "nano bananas", "cloud code"}
        if entity_name.lower() in google_tools:
            return []
        
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
    """Main enrichment pipeline combining detection, search, and relationship extraction."""

    BATCH_SIZE = 10  # max entities per LLM batch call (reduced for richer output)

    def __init__(self):
        self.detector = EntityDetector()
        self.searcher = WebSearcher()
        self.llm = LLMClient()

    async def enrich(self, chunks: list[DocumentChunk]) -> tuple[list[EnrichedEntity], list[ExtractedRelationship]]:
        """Enrich chunks with web search results, batch LLM descriptions, and relationships."""
        entity_map = self._detect_entities(chunks)

        # Extract URLs from OCR text and add as entities
        url_entities = self._extract_urls_from_chunks(chunks)
        for url_data in url_entities:
            key = url_data["name"].lower()
            if key not in entity_map:
                entity_map[key] = url_data
                logger.info(f"Extracted URL entity: {url_data['name']}")

        # Always run LLM extraction to catch new/unknown entities
        # Pattern detection only finds known entities - LLM finds everything
        llm_entities = await self._llm_extract_entities(chunks)
        for name, data in llm_entities.items():
            if name.lower() not in entity_map:
                entity_map[name.lower()] = data
            else:
                # Merge: keep higher confidence
                if data.get("confidence", 0) > entity_map[name.lower()].get("confidence", 0):
                    entity_map[name.lower()]["confidence"] = data["confidence"]

        if not entity_map:
            return [], []

        searched = await self._search_entities_concurrent(entity_map)
        descriptions = await self._generate_descriptions_batch(searched)
        enriched = self._assemble_enriched(searched, descriptions)

        # Extract relationships between entities
        relationships = await self._extract_relationships(enriched, chunks)

        # Extract step-by-step guides from video content
        steps = await self._extract_steps(chunks)

        return enriched, relationships, steps

    async def _extract_steps(self, chunks: list[DocumentChunk]) -> list[str]:
        """Extract step-by-step instructions from video transcript/OCR."""
        # Combine all text from chunks
        all_text = "\n\n".join(c.text for c in chunks)
        
        # Only extract steps if content looks like a tutorial/how-to
        tutorial_indicators = [
            "step", "how to", "tutorial", "guide", "instructions",
            "first", "then", "next", "finally", "copy", "paste",
            "click", "open", "go to", "visit"
        ]
        
        has_tutorial_content = any(ind in all_text.lower() for ind in tutorial_indicators)
        if not has_tutorial_content or len(all_text) < 100:
            return []

        try:
            from src.enrichment.llm_client import LLMClient
            llm = LLMClient()
            
            result = await llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract step-by-step instructions from this video content.\n\n"
                            "RULES:\n"
                            "- Only extract actionable steps (things the viewer should DO)\n"
                            "- Keep steps concise (1-2 sentences each)\n"
                            "- Include website/tool names exactly as mentioned\n"
                            "- Order steps chronologically\n"
                            "- Maximum 10 steps\n"
                            "- If no clear steps found, return empty array\n\n"
                            "Return a JSON object with a \"steps\" array of strings."
                        ),
                    },
                    {"role": "user", "content": f"Extract steps from this content:\n\n{all_text[:3000]}"},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            import json
            data = json.loads(result["content"])
            steps = data.get("steps", [])
            if steps:
                logger.info(f"Extracted {len(steps)} steps from content")
            return steps
            
        except Exception as e:
            logger.warning(f"Step extraction failed: {e}")
            return []

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

    async def _llm_extract_entities(self, chunks: list[DocumentChunk]) -> dict:
        """Use LLM to extract entities when pattern detection finds too few."""
        # Prioritize chunks with video/OCR content (most relevant for Reels)
        video_chunks = [c for c in chunks if any(marker in c.text for marker in 
            ["[Video Content]", "[Video Frame OCR]", "[Audio Transcript]", 
             "[English Transcript]", "[Hindi Translation]"])]
        
        if video_chunks:
            # Use video chunks first, they contain the actual screen recording content
            combined_text = "\n\n".join(c.text for c in video_chunks[:5])
            logger.info(f"LLM entity extraction using {len(video_chunks)} video chunks")
        else:
            combined_text = "\n\n".join(c.text for c in chunks[:5])
        
        if len(combined_text.strip()) < 50:
            return {}

        prompt = (
            "Extract ALL specific technical entities that are EXPLICITLY MENTIONED in this content. "
            "Focus on: tool names, website names, product names, framework names, library names.\n\n"
            "IMPORTANT:\n"
            "- ONLY extract entities that are ACTUALLY SHOWN or MENTIONED in the source content\n"
            "- Look for proper nouns and brand names visible on screen (e.g., 'Firecrawl', 'Localsend')\n"
            "- Look for website URLs or site names visible in screen recordings\n"
            "- Extract the EXACT names as they appear (preserve capitalization)\n"
            "- Do NOT extract generic terms (e.g., 'animations', 'CSS', 'websites')\n"
            "- Do NOT include programming languages (JavaScript, Python, etc.) - too generic\n"
            "- Do NOT include 'GitHub' unless a specific repository is mentioned\n"
            "- Do NOT include platform names (Instagram, Facebook, YouTube)\n"
            "- Do NOT include author/creator names\n"
            "- Do NOT guess or infer entities - only extract what is clearly visible\n"
            "- Maximum 10 entities\n\n"
            "Content:\n"
            f"{combined_text[:3000]}\n\n"
            "Return a JSON object with an \"entities\" array. Each entity has:\n"
            "- \"name\": the exact entity name as written\n"
            "- \"type\": one of [framework, library, tool, platform, service, "
            "database, concept, web_app, mobile_app, api, unknown]\n"
            "- \"confidence\": float 0.0-1.0\n\n"
            "Return ONLY valid JSON."
        )

        try:
            result = await self.llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical entity extractor. CRITICAL RULE: "
                            "ONLY extract entities that are EXPLICITLY SHOWN or MENTIONED in the content. "
                            "Do NOT guess, infer, or hallucinate entities. "
                            "If the content shows a video about Maya 3D rigs, extract 'Maya' and 'Agora Studio'. "
                            "Do NOT extract 'blender' if it's not mentioned. "
                            "Focus on tools, frameworks, libraries, platforms, and product names visible on screen. "
                            "Maximum 5. Return valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            content = result["content"].strip()

            # Parse JSON
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            elif not content.startswith("{"):
                brace_start = content.find("{")
                brace_end = content.rfind("}")
                if brace_start != -1 and brace_end != -1:
                    content = content[brace_start:brace_end + 1]

            data = json.loads(content)
            raw_entities = data.get("entities", [])

            # Convert to entity_map format with deduplication
            entity_map = {}
            for ent in raw_entities:
                name = ent.get("name", "").strip()
                if not name or len(name) < 2:
                    continue

                # Skip platform names
                name_lower = name.lower()
                if name_lower in {"instagram", "facebook", "twitter", "youtube",
                                   "tiktok", "linkedin", "reddit", ".app"}:
                    continue

                # Skip numeric facts (e.g., "48 chimneys", "35% less energy", "250+ animated components")
                if re.match(r'^[\d]+[%+]?\s+\w', name):
                    continue
                # Skip names that are just quantities or descriptions, not entities
                if re.match(r'^\d+\+?\s+(animated|free|best|top|new|all|more|less|best)', name, re.IGNORECASE):
                    continue

                # Skip generic UI/web terms that are features, not named entities
                generic_ui_terms = {
                    "hero sections", "hero section", "scroll effects", "scroll effect",
                    "landing pages", "landing page", "modern design blocks", "design blocks",
                    "animated components", "animations", "ui components", "web components",
                    "responsive design", "mobile first", "dark mode", "light mode",
                    "parallax", "fade in", "fade out", "slide in", "slide out",
                    "carousel", "slider", "modal", "popup", "tooltip", "dropdown",
                    "navigation", "header", "footer", "sidebar", "menu",
                    "button", "form", "input", "checkbox", "radio", "toggle",
                    "card", "grid", "flex", "layout", "container", "wrapper",
                    "typography", "font", "color", "gradient", "shadow",
                    "border", "radius", "padding", "margin", "spacing",
                    "animation", "transition", "transform", "keyframe",
                    "css", "html", "javascript", "typescript", "react", "vue", "angular",
                }
                if name_lower in generic_ui_terms:
                    continue
                # Skip multi-word phrases that are just feature descriptions
                if len(name.split()) > 3:
                    continue

                # Skip if similar to existing entity
                skip = False
                for existing_name in entity_map:
                    # Simple similarity: if one name contains the other
                    if name_lower in existing_name or existing_name in name_lower:
                        skip = True
                        break
                if skip:
                    continue

                type_str = ent.get("type", "unknown")
                try:
                    entity_type = EntityType(type_str)
                except ValueError:
                    entity_type = EntityType.UNKNOWN

                entity_map[name_lower] = {
                    "name": name,
                    "type": entity_type,
                    "context": combined_text[:300],
                    "confidence": float(ent.get("confidence", 0.7)),
                    "source_chunk_id": chunks[0].id if chunks else "",
                    "source_text": combined_text,
                    "source_chunks": [chunks[0].id] if chunks else [],
                }

                # Limit to 8 entities
                if len(entity_map) >= 8:
                    break

            logger.info(f"LLM extracted {len(entity_map)} entities")
            return entity_map

        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}")
            return {}

    def _extract_urls_from_chunks(self, chunks: list[DocumentChunk]) -> list[dict]:
        """Extract website URLs from OCR text in chunks."""
        import re
        url_entities = []
        
        # URL patterns to match
        url_patterns = [
            r'https?://[^\s<>"\']+',
            r'www\.[^\s<>"\']+',
            r'\b([a-zA-Z0-9-]+\.(com|org|net|io|dev|app|co))\b',
        ]
        
        # Common website name patterns (e.g., "Gumroad.com", "Agora.com")
        website_name_pattern = r'\b([A-Z][a-zA-Z0-9-]*\.(com|org|net|io|dev|app|co))\b'
        
        # OCR misread corrections
        ocr_corrections = {
            "animprops.com": "AnimWorkKes",
            "agora.com": "Agora.com",
            "gumroad.com": "Gumroad.com",
            "ora.com": "Agora.com",
            "animworks.com": "AnimWorkKes",
        }
        
        seen_urls = set()
        
        for chunk in chunks:
            text = chunk.text
            
            # Extract full URLs
            for pattern in url_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    url = match.group(0)
                    # Normalize URL
                    if not url.startswith('http'):
                        url = 'https://' + url
                    
                    # Skip common non-website URLs
                    skip_domains = {'instagram.com', 'facebook.com', 'twitter.com', 'youtube.com'}
                    if any(domain in url.lower() for domain in skip_domains):
                        continue
                    
                    if url.lower() not in seen_urls:
                        seen_urls.add(url.lower())
                        
                        # Extract domain name as entity name
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        domain = parsed.netloc or parsed.path
                        domain = domain.replace('www.', '')
                        
                        # Apply OCR corrections
                        domain_corrected = ocr_corrections.get(domain.lower(), domain)
                        
                        url_entities.append({
                            "name": domain_corrected,
                            "type": EntityType.WEB_APP,
                            "context": text[max(0, match.start()-100):match.end()+100],
                            "confidence": 0.95,  # High confidence for URLs
                            "source_chunk_id": chunk.id,
                            "source_text": chunk.text,
                            "source_chunks": [chunk.id],
                        })
            
            # Extract website names (e.g., "Gumroad.com")
            name_matches = re.finditer(website_name_pattern, text)
            for match in name_matches:
                website_name = match.group(1)
                # Apply OCR corrections
                website_name_corrected = ocr_corrections.get(website_name.lower(), website_name)
                
                if website_name_corrected.lower() not in seen_urls:
                    seen_urls.add(website_name_corrected.lower())
                    url_entities.append({
                        "name": website_name_corrected,
                        "type": EntityType.WEB_APP,
                        "context": text[max(0, match.start()-100):match.end()+100],
                        "confidence": 0.9,
                        "source_chunk_id": chunk.id,
                        "source_text": chunk.text,
                        "source_chunks": [chunk.id],
                    })
        
        logger.info(f"Extracted {len(url_entities)} URL entities from chunks")
        return url_entities

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
                    # Skip alternatives search - not needed for output
                    return {
                        **entity_data,
                        "search_results": search_results,
                        "alternatives": [],
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

            # Filter web_info to only include relevant references
            web_info = []
            for r in search_results:
                # Skip references from irrelevant domains
                url_lower = r.url.lower()
                title_lower = r.title.lower()
                
                # Domains to skip in references
                skip_domains = {
                    "whatsapp.com", "wa.me", "facebook.com", "twitter.com",
                    "instagram.com", "linkedin.com", "reddit.com", "quora.com",
                    "myntra.com", "ajio.com", "amazon.com", "flipkart.com",
                    "merriam-webster.com", "dictionary.com", "cambridge.org",
                    "wikipedia.org", "britannica.com",
                    "naukri.com", "indeed.com", "glassdoor.com",
                    "timesofindia.com", "hindustantimes.com", "ndtv.com",
                }
                
                is_skip_domain = False
                for domain in skip_domains:
                    if domain in url_lower:
                        is_skip_domain = True
                        break
                if is_skip_domain:
                    continue
                
                # Skip if title is too generic or irrelevant
                skip_title_patterns = [
                    "sign in", "log in", "login", "register",
                    "privacy policy", "terms of service",
                    "cookie", "advertisement",
                ]
                is_skip_title = False
                for pattern in skip_title_patterns:
                    if pattern in title_lower:
                        is_skip_title = True
                        break
                if is_skip_title:
                    continue
                
                web_info.append({
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": r.source,
                })

            # If no web_info from search, but entity was extracted from URL pattern
            # (confidence >= 0.9 indicates URL extraction), add the URL as web_info
            if not web_info and entity_data.get("confidence", 0) >= 0.9:
                name = entity_data["name"]
                # Check if name looks like a domain
                import re as re_module
                if re_module.match(r'^[a-zA-Z0-9-]+\.(com|org|net|io|dev|app|co)$', name):
                    web_info.append({
                        "title": name,
                        "url": f"https://{name}",
                        "snippet": f"Website found in video content",
                        "source": "ocr_extraction",
                    })

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
                f"  - {r.title}: {r.snippet[:300]}" for r in search_results[:4]
            )
            # Use full source text for context, not just the match window
            source_text = e.get("source_text", "")[:1500]
            entity_summaries.append(
                f"Name: {e['name']}\n"
                f"Type: {e['type']}\n"
                f"Source Content:\n{source_text}\n"
                f"Web Search Results:\n{search_ctx}"
            )

        entities_text = "\n\n".join(
            f"[Entity {i+1}]\n{summary}" for i, summary in enumerate(entity_summaries)
        )

        prompt = (
            "CRITICAL RULE: You MUST ONLY describe what is explicitly stated in the Source Content. "
            "Do NOT invent, hallucinate, or assume information that is NOT in the source.\n\n"
            "For each entity below, write a description that:\n"
            "1. States WHAT the entity IS based ONLY on the source content\n"
            "2. Describes what the source shows about this entity\n"
            "3. Mentions specific details from the source (e.g., 'the video shows X doing Y')\n"
            "4. If the source doesn't contain enough info, say so briefly\n\n"
            "DO NOT:\n"
            "- Make up features or capabilities not mentioned in the source\n"
            "- Describe generic use cases unrelated to the source\n"
            "- Add web search information that contradicts the source\n"
            "- Generate template descriptions (e.g., 'is a tool for X')\n\n"
            "The description should read like a summary of what the source content says about this entity.\n\n"
            f"Return a JSON object with a \"descriptions\" array containing "
            f"exactly {len(batch)} strings, in the same order as the entities.\n\n"
            f"Example:\n"
            f'Entity: Maya\n'
            f'Source: "Agora Studio showcases Maya rigs for 3D animation, including Gamma and Alpha characters"\n'
            f'Description: "Maya is shown in the source as the 3D animation software used by Agora Studio. '
            f'The video demonstrates Maya rigs including the Gamma character (first in the Agora Original Rigs family) '
            f'and Alpha character. Various Maya rigs are displayed on Gumroad.com for purchase."\n\n'
            f"Entities:\n{entities_text}\n\n"
            "Return ONLY valid JSON."
        )

        try:
            result = await self.llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical knowledge graph builder. CRITICAL RULE: "
                            "You MUST ONLY describe what is explicitly stated in the Source Content. "
                            "Do NOT invent information not present in the source. "
                            "Write descriptions that accurately summarize what the source says about each entity. "
                            "If the source shows a video about Maya rigs, say 'Maya is shown as the 3D software used for rigs'. "
                            "Do NOT add generic descriptions like 'React hooks' or 'state management' if the source doesn't mention them. "
                            "Write 2-4 sentences per entity. Return valid JSON with a \"descriptions\" array."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=600 * len(batch),
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

            # Handle Ollama returning dicts instead of strings
            normalized = []
            for d in descriptions:
                if isinstance(d, dict):
                    # Extract the description text from dict
                    normalized.append(d.get("description", d.get("summary", str(d))))
                else:
                    normalized.append(str(d))
            descriptions = normalized

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
            # Try to extract partial JSON before giving up
            try:
                import re as re_module
                raw = re_module.search(r'```json\s*\n(.*?)$', response_text, re_module.DOTALL)
                if raw:
                    descs = re_module.findall(r'"description"\s*:\s*"([^"]*)"', raw.group(1))
                    if descs:
                        logger.info(f"Recovered {len(descs)} descriptions from partial JSON")
                        while len(descs) < len(batch):
                            idx = len(descs)
                            descs.append(
                                f"{batch[idx]['name']} is a "
                                f"{batch[idx]['type']} in the source content."
                            )
                        return descs[:len(batch)]
            except Exception:
                pass
            return [
                f"{e['name']} is a {e['type']} mentioned in the source content."
                for e in batch
            ]

    async def _extract_relationships(
        self, entities: list[EnrichedEntity], chunks: list[DocumentChunk]
    ) -> list[ExtractedRelationship]:
        """Extract relationships between entities using LLM."""
        if len(entities) < 2:
            return []

        all_relationships = []

        # Process in batches of 20 entities at a time
        batch_size = 20
        for batch_start in range(0, len(entities), batch_size):
            batch = entities[batch_start:batch_start + batch_size]
            batch_rels = await self._llm_extract_relationships(batch, chunks)
            all_relationships.extend(batch_rels)

        return all_relationships

    async def _llm_extract_relationships(
        self, entities: list[EnrichedEntity], chunks: list[DocumentChunk]
    ) -> list[ExtractedRelationship]:
        """Single LLM call to extract relationships between entities."""
        # Build entity list with context
        entity_list = "\n".join(
            f"- {e.name} ({e.type.value}): {e.description[:200]}"
            for e in entities
        )

        # Combine source texts for context
        source_texts = "\n\n".join(
            f"[Chunk {i+1}]: {c.text[:500]}"
            for i, c in enumerate(chunks[:5])
        )

        prompt = (
            "Given these entities from the same content, extract ALL meaningful "
            "relationships between them. Relationship types to consider:\n\n"
            "- USES: A uses B (e.g., 'React uses JSX', 'Docker uses Kubernetes')\n"
            "- DEPENDS_ON: A depends on B (e.g., 'App depends on Database')\n"
            "- IMPLEMENTS: A implements B (e.g., 'Express implements HTTP server')\n"
            "- REPLACES: A replaces B (e.g., 'Vercel replaces Heroku')\n"
            "- INTEGRATES_WITH: A integrates with B (e.g., 'Stripe integrates with React')\n"
            "- PART_OF: A is part of B (e.g., 'React hooks are part of React')\n"
            "- ALTERNATIVE_TO: A is an alternative to B (e.g., 'Vue is alternative to React')\n"
            "- ENABLES: A enables B (e.g., 'Docker enables containerization')\n"
            "- EVOLVED_FROM: A evolved from B (e.g., 'Next.js evolved from Create React App')\n"
            "- COMPLEMENTS: A complements B (e.g., 'TypeScript complements JavaScript')\n\n"
            f"Entities:\n{entity_list}\n\n"
            f"Source Content:\n{source_texts}\n\n"
            f"Return a JSON object with a \"relationships\" array. Each relationship has:\n"
            f"- \"source\": name of entity A\n"
            f"- \"target\": name of entity B\n"
            f"- \"relation_type\": one of the types above\n"
            f"- \"description\": brief explanation of the relationship\n"
            f"- \"confidence\": float 0.0-1.0\n\n"
            f"Only include relationships you are confident about. "
            f"Return ONLY valid JSON."
        )

        try:
            result = await self.llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical knowledge graph builder specializing in "
                            "software engineering relationships. Extract precise, factual "
                            "relationships between entities. Focus on USES, DEPENDS_ON, "
                            "IMPLEMENTS, INTEGRATES_WITH, and ALTERNATIVE_TO relationships. "
                            "Only include relationships you are confident about from the "
                            "context. Return valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = result["content"].strip()

            # Parse JSON
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            elif not content.startswith("{"):
                brace_start = content.find("{")
                brace_end = content.rfind("}")
                if brace_start != -1 and brace_end != -1:
                    content = content[brace_start:brace_end + 1]

            data = json.loads(content)
            raw_rels = data.get("relationships", [])

            # Validate and convert
            entity_names = {e.name.lower() for e in entities}
            relationships = []
            for rel in raw_rels:
                source = rel.get("source", "").strip()
                target = rel.get("target", "").strip()
                rel_type = rel.get("relation_type", "").strip().upper()

                # Validate names exist in our entity set
                if (source.lower() in entity_names and
                    target.lower() in entity_names and
                    source.lower() != target.lower()):
                    relationships.append(ExtractedRelationship(
                        source=source,
                        target=target,
                        relation_type=rel_type,
                        description=rel.get("description", ""),
                        confidence=float(rel.get("confidence", 0.7)),
                    ))

            return relationships

        except Exception as e:
            logger.warning(f"Relationship extraction failed: {e}")
            return []

    async def close(self):
        await self.searcher.close()
        await self.llm.close()
