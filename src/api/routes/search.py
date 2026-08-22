"""Search routes."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Query

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
    """Hybrid search combining vector, fulltext, and graph signals.

    Supports pagination via limit and offset query parameters.
    """
    query = request.get("query", "")
    
    hybrid_searcher = get_searcher()
    
    try:
        results = await hybrid_searcher.search(query, limit=limit + offset)
        # Apply pagination
        paginated = results[offset:offset + limit]
        return {
            "results": paginated,
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(results),
        }
    except Exception:
        try:
            results = await db.search_entities(query, limit=limit + offset)
            paginated = results[offset:offset + limit]
            return {
                "results": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "description": r.description,
                        "entity_type": r.entity_type_id,
                    }
                    for r in paginated
                ],
                "total": len(results),
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(results),
            }
        except Exception:
            return {"results": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}
