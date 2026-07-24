import asyncio
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from src.config import get_settings
from src.config.models import DocumentChunk, EnrichedEntity, EntityType
from src.enrichment.llm_client import LLMClient
from loguru import logger


settings = get_settings()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str


class EntityDetector:
    """Detect web/app/tool mentions in text."""
    
    ENTITY_PATTERNS = {
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
            r"\b(stripe|auth0|clerk|supabase|firebase|planetscale|neon|supabase)\b",
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
            r"\b(saas|dashboard|admin panel|web app|platform)\b",
        ],
        EntityType.MOBILE_APP: [
            r"\b(react native|expo|flutter|ios|android|swift|kotlin)\b",
        ],
        EntityType.LANGUAGE: [
            r"\b(typescript|javascript|python|rust|go|golang|java|kotlin)\b",
        ],
        EntityType.API: [
            r"\b(rest|graphql|grpc|webhook|api)\b",
        ],
    }
    
    # Known entities for boosting
    KNOWN_ENTITIES = {
        "react", "vue", "svelte", "angular", "next.js", "nuxt", "astro", "remix",
        "django", "fastapi", "flask", "express", "nest.js", "spring", "laravel",
        "tailwind", "bootstrap", "material-ui", "chakra", "shadcn", "radix",
        "prisma", "drizzle", "sqlalchemy", "typeorm", "mongoose",
        "postgresql", "mysql", "mongodb", "redis", "sqlite", "planetscale", "neon",
        "aws", "gcp", "azure", "vercel", "netlify", "railway", "render", "fly.io",
        "kubernetes", "docker", "terraform", "ansible",
        "stripe", "auth0", "clerk", "supabase", "firebase", "planetscale",
        "github", "gitlab", "bitbucket",
        "vscode", "intellij", "vim", "neovim", "cursor", "windsurf",
        "jest", "vitest", "playwright", "cypress", "pytest",
        "react native", "expo", "flutter",
        "typescript", "javascript", "python", "rust", "go", "java", "kotlin",
    }

    def detect(self, text: str, max_entities: int = 20) -> List[Dict[str, Any]]:
        """Detect tech entities in text."""
        detected = []
        text_lower = text.lower()
        
        # Pattern-based detection
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
                for match in matches:
                    entity_name = self._extract_name(text, match.start(), match.end())
                    if entity_name and len(entity_name) > 1:
                        detected.append({
                            "name": entity_name,
                            "type": entity_type,
                            "context": text[max(0, match.start()-100):match.end()+100],
                            "confidence": 0.8
                        })
        
        # Boost known entities
        for known in self.KNOWN_ENTITIES:
            if known.lower() in text_lower:
                # Check if already detected
                if not any(d["name"].lower() == known.lower() for d in detected):
                    detected.append({
                        "name": known,
                        "type": self._guess_type(known),
                        "context": f"Known entity: {known}",
                        "confidence": 0.9
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
    
    def _extract_name(self, text: str, start: int, end: int) -> str:
        """Extract entity name from context around match."""
        # Get wider context
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = text[context_start:context_end]
        
        # Try to find capitalized words near the match
        words = re.findall(r'\b[A-Z][a-zA-Z0-9\-\.]*\b', context)
        if words:
            return words[0]
        
        # Fallback to matched text
        matched = text[start:end].strip()
        return matched if matched else "unknown"
    
    def _guess_type(self, name: str) -> EntityType:
        """Guess entity type from name."""
        name_lower = name.lower()
        
        if name_lower in {"react", "vue", "svelte", "angular", "next.js", "nuxt", "django", "fastapi", "express"}:
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
        return EntityType.UNKNOWN


class WebSearcher:
    """Search the web for entity information."""
    
    def __init__(self):
        self.ddgs = DDGS()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; InstaGPT-GraphRAG/0.1)"}
        )
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using DuckDuckGo."""
        results = []
        
        try:
            # DDGS search
            ddgs_results = self.ddgs.text(query, max_results=max_results)
            
            for r in ddgs_results:
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                    source="duckduckgo"
                ))
        except Exception as e:
            logger.warning(f"DDGS search failed: {e}")
        
        return results
    
    async def search_entity(self, entity_name: str, entity_type: EntityType) -> List[SearchResult]:
        """Search for specific entity info."""
        type_keywords = {
            EntityType.FRAMEWORK: "framework features documentation",
            EntityType.LIBRARY: "library npm package documentation",
            EntityType.TOOL: "tool features pricing alternatives",
            EntityType.PLATFORM: "platform pricing features comparison",
            EntityType.SERVICE: "service pricing features api",
            EntityType.DATABASE: "database features pricing comparison",
        }
        
        keyword = type_keywords.get(entity_type, "features pricing alternatives")
        query = f"{entity_name} {keyword}"
        
        return await self.search(query, max_results=8)
    
    async def find_alternatives(self, entity_name: str, entity_type: EntityType) -> List[Dict[str, Any]]:
        """Find similar/alternative tools."""
        query = f"{entity_name} alternatives competitors similar"
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
    
    def _extract_alternatives(self, text: str, exclude: str) -> List[str]:
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
        
        # Filter out common words
        filtered = [f for f in found if len(f) > 2 and f.lower() not in 
                   {"the", "and", "or", "but", "for", "with", "from", "this", "that"}]
        
        return list(set(filtered))[:5]
    
    async def close(self):
        await self.client.aclose()


class EnrichmentPipeline:
    """Main enrichment pipeline combining detection and search."""
    
    def __init__(self):
        self.detector = EntityDetector()
        self.searcher = WebSearcher()
        self.llm = LLMClient()
    
    async def enrich(self, chunks: List[DocumentChunk]) -> List[EnrichedEntity]:
        """Enrich chunks with web search results."""
        all_entities = []
        
        # Detect entities from all chunks
        for chunk in chunks:
            detected = self.detector.detect(chunk.text)
            for det in detected:
                det["source_chunk_id"] = chunk.id
            all_entities.extend(detected)
        
        # Deduplicate across chunks
        entity_map = {}
        for det in all_entities:
            key = det["name"].lower()
            if key not in entity_map:
                entity_map[key] = det
                entity_map[key]["source_chunks"] = [det["source_chunk_id"]]
            else:
                entity_map[key]["source_chunks"].append(det["source_chunk_id"])
                # Merge contexts
                entity_map[key]["context"] += " ... " + det["context"]
        
        # Enrich each unique entity
        enriched = []
        for entity_data in entity_map.values():
            try:
                enriched_entity = await self._enrich_entity(entity_data)
                enriched.append(enriched_entity)
            except Exception as e:
                logger.warning(f"Failed to enrich {entity_data['name']}: {e}")
        
        return enriched
    
    async def _enrich_entity(self, entity_data: Dict) -> EnrichedEntity:
        """Enrich a single entity with web search."""
        name = entity_data["name"]
        entity_type = entity_data["type"]
        context = entity_data["context"]
        source_chunk_id = entity_data["source_chunks"][0]
        source_chunks = entity_data["source_chunks"]
        
        # Search for entity info
        search_results = await self.searcher.search_entity(name, entity_type)
        
        # Find alternatives
        alternatives = await self.searcher.find_alternatives(name, entity_type)
        
        # Use LLM to generate description and synthesize info
        description = await self._generate_description(name, entity_type, context, search_results)
        
        # Format web info
        web_info = [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source": r.source
            }
            for r in search_results
        ]
        
        # Format similar tools
        similar_tools = [
            {
                "name": a["name"],
                "description": a["description"],
                "url": a["url"]
            }
            for a in alternatives
        ]
        
        return EnrichedEntity(
            name=name,
            type=entity_type,
            description=description,
            web_info=web_info,
            similar_tools=similar_tools,
            source_chunk_id=source_chunk_id,
            source_url=search_results[0].url if search_results else "",
            confidence=entity_data["confidence"]
        )
    
    async def _generate_description(
        self, 
        name: str, 
        entity_type: EntityType, 
        context: str,
        search_results: List[SearchResult]
    ) -> str:
        """Generate entity description using LLM."""
        search_context = "\n".join([
            f"- {r.title}: {r.snippet[:300]}" 
            for r in search_results[:5]
        ])
        
        prompt = f"""
        Write a concise technical description of "{name}" ({entity_type.value}):
        
        Original context: {context[:500]}
        
        Web search results:
        {search_context}
        
        Write 2-3 sentences covering:
        1. What it is
        2. Key features/purpose
        3. Notable characteristics
        
        Be factual and concise. No marketing fluff.
        """
        
        try:
            result = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=settings.OPENAI_CHAT_MODEL,
                temperature=0.2,
                max_tokens=200
            )
            return result["content"].strip()
        except Exception as e:
            logger.warning(f"LLM description failed for {name}: {e}")
            return f"{name} is a {entity_type.value} mentioned in the source content."
    
    async def close(self):
        await self.searcher.close()
        await self.llm.close()