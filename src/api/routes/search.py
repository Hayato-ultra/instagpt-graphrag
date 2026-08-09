"""Search routes."""
from typing import Dict, Any
from fastapi import APIRouter, Depends

from src.database import CRUDOperations, get_async_session


router = APIRouter(prefix="/api", tags=["search"])


def get_searcher():
    """Get hybrid searcher from app state."""
    from src.api import searcher
    return searcher


@router.post("/search")
async def search(
    request: Dict[str, Any],
    db: CRUDOperations = Depends(get_async_session),
):
    """Hybrid search combining vector, fulltext, and graph signals."""
    query = request.get("query", "")
    
    hybrid_searcher = get_searcher()
    
    try:
        results = await hybrid_searcher.search(query, limit=20)
        return {"results": results[:20], "total": len(results)}
    except Exception:
        # Fallback to PostgreSQL search
        try:
            results = await db.search_entities(query, limit=20)
            return {
                "results": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "description": r.description,
                        "entity_type": r.entity_type_id,
                    }
                    for r in results
                ],
                "total": len(results),
            }
        except Exception:
            return {"results": [], "total": 0}
