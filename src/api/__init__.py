"""FastAPI backend for InstaGPT GraphRAG.

Routes are organized in src/api/routes/:
- video.py: Video analysis endpoints
- graph.py: Knowledge graph endpoints
- search.py: Hybrid search endpoints
- notebook.py: Notebook endpoints
- jobs.py: Pipeline job list/detail/retry endpoints

This file contains:
- App initialization and lifespan (with crash recovery)
- Background task processing using PipelineJob + checkpoints
- Extra endpoints (stats, content details)
"""
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import uuid

from src.api.routes import graph_router, jobs_router, notebook_router, search_router, video_router
from src.config import get_settings
from src.database import CRUDOperations, close_db, get_async_session, init_db
from src.graph import Neo4jGraphStore
from src.pipeline import KnowledgeGraphPipeline
from src.pipeline.outbox import OutboxWorker, build_projector, persist_and_publish
from src.pipeline.recorder import SQLPipelineRecorder
from src.search import HybridSearcher

settings = get_settings()

pipeline: KnowledgeGraphPipeline | None = None
graph_store: Neo4jGraphStore | None = None
searcher: HybridSearcher | None = None


async def get_db():
    """Dependency to get database session."""
    async for session in get_async_session():
        yield CRUDOperations(session)


async def recover_stuck_jobs() -> int:
    """Reset jobs stuck in PROCESSING (crashed workers) back to PENDING."""
    from src.database.base import _session_factory

    async with _session_factory() as session:
        db = CRUDOperations(session)
        try:
            count = await db.reset_stuck_jobs(stale_seconds=600)
            if count:
                logger.warning(f"Crash recovery: reset {count} stuck jobs back to PENDING")
            await session.commit()
            return count
        except Exception as e:
            logger.error(f"Crash recovery failed: {e}")
            await session.rollback()
            return 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, graph_store, searcher

    await init_db()

    # Recover any jobs stuck in PROCESSING from a previous crash
    await recover_stuck_jobs()

    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()
    graph_store = pipeline.graph_store

    searcher = HybridSearcher(
        vector_store=pipeline.vector_store,
        graph_store=graph_store,
        embedder=pipeline.embedder,
    )

    yield

    if pipeline:
        await pipeline.close()
    await close_db()


app = FastAPI(
    title="InstaGPT GraphRAG API",
    description="URL to Knowledge Graph Pipeline",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request ID Middleware (TODO #51 observability) ---

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Bind request_id to loguru context for correlated logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        with logger.contextualize(request_id=request_id):
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)


# --- Rate Limiting Middleware (TODO #65) ---

from collections import defaultdict
import time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter.

    Args:
        max_requests: Max requests per window per client IP.
        window_seconds: Sliding window size in seconds.
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window_seconds

        # Prune old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > cutoff
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)


# Include route modules
app.include_router(video_router)
app.include_router(graph_router)
app.include_router(search_router)
app.include_router(notebook_router)
app.include_router(jobs_router)


# --- Health Check (TODO #61) ---

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "ok", "version": "0.3.0"}


# --- Background Task ---

async def process_video_task(job_id: str, url: str):
    """Background task: run pipeline with per-step checkpointing via PipelineJob.

    Each completed stage is persisted to PostgreSQL. If the worker crashes,
    recover_stuck_jobs resets RUNNING steps to PENDING, and this task
    re-runs only the incomplete stages.

    On success, entities/relationships are persisted to PG and outbox events
    are published atomically; pending events are then drained so the Neo4j and
    Qdrant projections are rebuilt idempotently.
    """
    from src.database.base import _session_factory

    async with _session_factory() as session:
        db = CRUDOperations(session)
        try:
            # Claim the job (PENDING→PROCESSING, sets started_at + heartbeat)
            job = await db.claim_pipeline_job(job_id)
            if not job:
                logger.warning(f"Could not claim job {job_id} — may already be processing")
                return

            await session.commit()

            # Create a recorder bound to this job
            recorder = SQLPipelineRecorder(db, job_id)

            result = await pipeline.process_url(url, recorder=recorder, db=db)

            if result.success:
                processing = result.processing_result

                # Persist extracted content to Postgres (source of truth)
                content = processing.extracted_content if processing else None
                content_record = await db.create_content(
                    url=url,
                    title=content.title if content else "Unknown",
                    raw_text=content.raw_text if content else "",
                    content_length=len(content.raw_text) if content else 0,
                )

                # Persist entities/relationships and publish outbox events in the
                # SAME transaction as the content row (atomic source-of-truth write).
                counts = {"entities": 0, "relationships": 0, "chunks": 0}
                if processing:
                    counts = await persist_and_publish(
                        crud=db,
                        content_id=content_record.id,
                        categorized=processing.categorized_items,
                        relationships=processing.relationships,
                        chunks=processing.chunks,
                    )
                logger.info(f"Outbox events published for {job_id}: {counts}")

                await db.complete_pipeline_job(job_id)
            else:
                # Check if we've exhausted attempts
                job = await db.get_pipeline_job_by_id(job_id)
                dead_letter = job and job.attempt >= (job.max_attempts or 3)
                await db.fail_pipeline_job(
                    job_id, error=result.error or "Unknown error", dead_letter=dead_letter
                )

        except Exception as e:
            logger.error(f"process_video_task crashed: {e}")
            with suppress(Exception):
                await db.fail_pipeline_job(job_id, error=str(e), dead_letter=False)
        finally:
            try:
                await session.commit()
            except Exception:
                await session.rollback()
            await session.close()

    # Drain the outbox after the source-of-truth transaction commits.
    try:
        async with _session_factory() as session:
            worker = OutboxWorker(
                crud=CRUDOperations(session),
                projector=build_projector(
                    graph_store=pipeline.graph_store if pipeline else None,
                    vector_store=pipeline.vector_store if pipeline else None,
                    embedder=pipeline.embedder if pipeline else None,
                ),
            )
            drained = await worker.drain(max_events=1000)
            await session.commit()
        logger.info(f"Outbox drain for {job_id}: {drained}")
    except Exception as e:
        logger.error(f"Outbox drain failed for {job_id}: {e}")


# --- Extra Endpoints (not in route modules) ---

@app.get("/api/stats")
async def get_stats(db: CRUDOperations = Depends(get_db)):
    """Get database statistics."""
    return await db.get_stats()


@app.get("/api/content/{content_id}/entities")
async def get_content_entities(
    content_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get entities linked to content."""
    content = await db.get_content_by_id(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    # Use content_entities relationship
    entities = []
    for ce in content.content_entities:
        if ce.entity:
            entities.append({
                "id": ce.entity.id,
                "name": ce.entity.name,
                "description": ce.entity.description,
                "confidence": ce.entity.confidence,
            })
    return {
        "content_id": content_id,
        "entities": entities,
        "total": len(entities),
    }


@app.get("/api/content/{content_id}/steps")
async def get_content_steps(
    content_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get processing steps for content."""
    content = await db.get_content_by_id(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Find the most recent pipeline job for this URL
    jobs = await db.list_pipeline_jobs(limit=100)
    steps = []
    for job in jobs:
        if job.url == content.url:
            pipeline_steps = await db.get_pipeline_steps(job.id)
            steps = [
                {"name": s.step_name, "status": s.status.value, "order": s.step_order}
                for s in pipeline_steps
            ]
            break

    return {
        "content_id": content_id,
        "url": content.url,
        "title": content.title,
        "steps": steps,
        "total_steps": len(steps),
    }
