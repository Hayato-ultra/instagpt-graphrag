"""Pipeline job management routes.

List jobs, view step checkpoints, retry failed/dead-letter jobs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.routes import get_db
from src.database import CRUDOperations

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/")
async def list_jobs(
    status: str | None = Query(None, description="Filter by status: pending, processing, completed, failed, dead_letter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: CRUDOperations = Depends(get_db),
):
    """List pipeline jobs with optional status filter."""
    jobs = await db.list_pipeline_jobs(status=status, limit=limit, offset=offset)
    return [
        {
            "id": job.id,
            "url": job.url,
            "content_hash": job.content_hash,
            "status": job.status.value,
            "current_step": job.current_step,
            "priority": job.priority,
            "attempt": job.attempt,
            "max_attempts": job.max_attempts,
            "error": job.error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
        for job in jobs
    ]


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get a single pipeline job with its step details."""
    job = await db.get_pipeline_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    steps = await db.get_pipeline_steps(job_id)
    return {
        "id": job.id,
        "url": job.url,
        "content_hash": job.content_hash,
        "status": job.status.value,
        "current_step": job.current_step,
        "priority": job.priority,
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "error": job.error,
        "result_metadata": job.result_metadata,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        "steps": [
            {
                "name": s.step_name,
                "status": s.status.value,
                "order": s.step_order,
                "attempt": s.attempt,
                "error": s.error,
                "checkpoint_data": s.checkpoint_data,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in steps
        ],
    }


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    background_tasks: "BackgroundTasks" = None,
    db: CRUDOperations = Depends(get_db),
):
    """Retry a failed or dead-letter job.

    Resets the job to PENDING and re-enqueues it for background processing.
    """
    from src.api import process_video_task

    job = await db.reset_job_for_retry(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or not in a retryable state (must be failed/dead_letter)",
        )
    await db.session.commit()

    if background_tasks:
        background_tasks.add_task(process_video_task, job.id, job.url)

    return {
        "id": job.id,
        "status": job.status.value,
        "attempt": job.attempt,
        "message": "Job re-queued for processing",
    }
