"""Notebook routes."""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from src.database import CRUDOperations, get_async_session


router = APIRouter(prefix="/api/notebook", tags=["notebook"])


@router.get("/")
async def list_notebook(
    db: CRUDOperations = Depends(get_async_session),
):
    """List notebook entries."""
    contents = await db.list_content(limit=100)
    entries = []
    for c in contents:
        entries.append({
            "id": c.id,
            "video_id": c.id,
            "title": c.title,
            "summary": c.summary,
            "ai_notes": "",
            "links": "",
            "tags": "",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"entries": entries, "total": len(entries)}


@router.get("/{entry_id}")
async def get_notebook_entry(
    entry_id: str,
    db: CRUDOperations = Depends(get_async_session),
):
    """Get a single notebook entry."""
    content = await db.get_content(entry_id)
    if not content:
        raise HTTPException(status_code=404, detail="Notebook entry not found")
    return {
        "id": content.id,
        "video_id": content.id,
        "title": content.title,
        "summary": content.summary,
        "ai_notes": "",
        "links": "",
        "tags": "",
        "created_at": content.created_at.isoformat() if content.created_at else None,
    }
