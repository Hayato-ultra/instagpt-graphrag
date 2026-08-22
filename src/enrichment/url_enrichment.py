"""Entity URL enrichment — find website URLs for extracted entities (TODO #26).

Replaces Instagram source URLs with entity's official website.
"""
from __future__ import annotations

from loguru import logger

from src.enrichment.enrichment import WebSearcher


async def enrich_entity_urls(
    entities: list[dict],
    searcher: WebSearcher | None = None,
) -> list[dict]:
    """Add official URLs to entities that are missing them (TODO #26).

    Args:
        entities: list of entity dicts with 'name', 'type', etc.
        searcher: optional WebSearcher instance.

    Returns:
        Entities with 'url' field populated where possible.
    """
    if not entities:
        return entities

    if searcher is None:
        searcher = WebSearcher()

    enriched = []
    for entity in entities:
        entity = dict(entity)  # Don't mutate original

        # Skip if already has a good URL
        existing_url = entity.get("url", "")
        if existing_url and "instagram.com" not in existing_url:
            enriched.append(entity)
            continue

        # Search for entity URL
        name = entity.get("name", "")
        etype = entity.get("type", "")

        if not name:
            enriched.append(entity)
            continue

        # Skip generic concepts that don't have URLs
        skip_types = {"concept", "principle", "technique", "unknown"}
        if etype in skip_types:
            enriched.append(entity)
            continue

        try:
            url = await searcher.search_entity_url(name, etype)
            if url:
                entity["url"] = url
                logger.debug(f"Found URL for '{name}': {url}")
            else:
                logger.debug(f"No URL found for '{name}'")
        except Exception as e:
            logger.warning(f"URL search failed for '{name}': {e}")

        enriched.append(entity)

    url_count = sum(1 for e in enriched if e.get("url"))
    logger.info(f"URL enrichment: {url_count}/{len(enriched)} entities have URLs")
    return enriched
