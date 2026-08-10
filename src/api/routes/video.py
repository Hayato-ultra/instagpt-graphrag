"""Video analysis routes."""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from src.api.routes import get_db
from src.database import CRUDOperations, get_async_session


router = APIRouter(prefix="/api/video", tags=["video"])


@router.post("/analyze")
async def analyze_video(
    request: Dict[str, str],
    background_tasks: BackgroundTasks,
    db: CRUDOperations = Depends(get_db),
):
    """Start analyzing a video URL."""
    from src.api import process_video_task
    
    url = request.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    job = await db.create_analysis_job(url=url)
    await db.session.commit()
    
    background_tasks.add_task(process_video_task, job.id, url)
    
    return {
        "analysis_id": job.id,
        "status": "processing",
        "stage": "starting",
    }


@router.get("/analysis/{analysis_id}")
async def get_analysis_status(
    analysis_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get analysis status."""
    job = await db.get_job(analysis_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "analysis_id": job.id,
        "status": job.status,
        "stage": job.stage,
        "url": job.url,
        "content_id": job.content_id,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/{content_id}")
async def get_video(
    content_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get video details."""
    content = await db.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Video not found")
    return {
        "id": content.id,
        "url": content.url,
        "title": content.title,
        "summary": content.summary,
        "entities_count": content.entities_count,
        "created_at": content.created_at.isoformat() if content.created_at else None,
    }


@router.get("/")
async def list_videos(
    limit: int = 100,
    offset: int = 0,
    db: CRUDOperations = Depends(get_db),
):
    """List all processed videos."""
    contents = await db.list_content(limit=limit, offset=offset)
    return [
        {
            "id": c.id,
            "url": c.url,
            "title": c.title,
            "summary": c.summary,
            "entities_count": c.entities_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in contents
    ]
