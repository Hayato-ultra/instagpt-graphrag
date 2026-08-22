"""Video analysis routes.

Preserves the existing JSON contract for the frontend while using
PipelineJob internally for checkpoint/resume support.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.api.routes import get_db
from src.database import CRUDOperations
from src.pipeline import STAGE_NAMES, content_hash

router = APIRouter(prefix="/api/video", tags=["video"])


@router.post("/analyze")
async def analyze_video(
    request: dict[str, str],
    background_tasks: BackgroundTasks,
    db: CRUDOperations = Depends(get_db),
):
    """Start analyzing a video URL.

    Idempotent: if the same URL was already submitted, returns the existing
    analysis_id and status without creating a duplicate job.
    """
    url = request.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    c_hash = content_hash(url)

    # Idempotency: return existing job if one exists for this URL
    existing = await db.get_pipeline_job_by_hash(c_hash)
    if existing:
        return {
            "analysis_id": existing.id,
            "status": existing.status.value,
            "stage": existing.current_step or "starting",
        }

    # Create new PipelineJob with pre-created step records
    job = await db.create_pipeline_job(
        content_hash=c_hash,
        url=url,
        steps=STAGE_NAMES,
    )
    # Commit immediately so the job is visible before the background task reads it
    from src.database.base import _session_factory
    async with _session_factory() as session:
        await session.commit()

    background_tasks.add_task(_run_pipeline_task, job.id, url)

    return {
        "analysis_id": job.id,
        "status": "processing",
        "stage": "starting",
    }


def _run_pipeline_task(job_id: str, url: str):
    """Run the pipeline in a background task (imported lazily to avoid cycles)."""
    from src.api import process_video_task

    return process_video_task(job_id, url)


@router.get("/analysis/{analysis_id}")
async def get_analysis_status(
    analysis_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get analysis status.

    Returns the same JSON shape the frontend expects, reading from PipelineJob.
    """
    job = await db.get_pipeline_job_by_id(analysis_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Build stage list from pipeline_steps
    steps = await db.get_pipeline_steps(analysis_id)
    stages = [
        {"name": s.step_name, "status": s.status.value, "order": s.step_order}
        for s in steps
    ]

    return {
        "analysis_id": job.id,
        "status": job.status.value,
        "stage": (
            job.current_step
            or ("completed" if job.status.value == "completed" else "processing")
        ),
        "url": job.url,
        "content_id": None,  # Not linked to content table in new path yet
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "stages": stages,
        "attempt": job.attempt,
    }


@router.get("/{content_id}")
async def get_video(
    content_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get video details."""
    content = await db.get_content_by_id(content_id)
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
