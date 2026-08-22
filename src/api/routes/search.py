"""Search routes."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Query
from loguru import logger

from src.api.routes import get_db
from src.database import CRUDOperations


router = APIRouter(prefix="/api", tags=["search"])


def get_searcher():
    """Get hybrid searcher from app state."""
    from src.api import searcher
    return searcher


@router.post("/search")
async def search(
    request: Dict[str, Any],
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Result offset for pagination"),
    db: CRUDOperations = Depends(get_db),
):
    """Hybrid search combining vector, fulltext, and graph signals."""
    query = request.get("query", "").strip()
    if not query:
        return {"results": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}

    hybrid_searcher = get_searcher()

    # Try hybrid search first
    if hybrid_searcher:
        try:
            results = await hybrid_searcher.search(query, limit=limit + offset)
            if results:
                paginated = results[offset:offset + limit]
                return {
                    "results": paginated,
                    "total": len(results),
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < len(results),
                }
        except Exception as e:
            logger.warning(f"Hybrid search failed: {e}")

    # Fallback: direct DB search
    try:
        results = await db.search_entities(query, limit=limit + offset)
        paginated = results[offset:offset + limit]
        return {
            "results": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description or "",
                    "entity_type": r.entity_type.name if hasattr(r, 'entity_type') and r.entity_type else "",
                    "score": 1.0,
                    "source": "db",
                }
                for r in paginated
            ],
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(results),
        }
    except Exception as e:
        logger.error(f"DB search failed: {e}")

    # Final fallback: empty
    return {"results": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}
