"""FastAPI backend for InstaGPT GraphRAG.

Routes are organized in src/api/routes/:
- video.py: Video analysis endpoints
- graph.py: Knowledge graph endpoints
- search.py: Hybrid search endpoints
- notebook.py: Notebook endpoints

This file contains:
- App initialization and lifespan
- Background task processing
- Extra endpoints (stats, content details)
"""
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.pipeline import KnowledgeGraphPipeline
from src.graph import Neo4jGraphStore
from src.database import CRUDOperations, get_async_session, init_db, close_db
from src.search import HybridSearcher
from src.api.routes import video_router, graph_router, search_router, notebook_router


settings = get_settings()

pipeline: Optional[KnowledgeGraphPipeline] = None
graph_store: Optional[Neo4jGraphStore] = None
searcher: Optional[HybridSearcher] = None


async def get_db():
    """Dependency to get database session."""
    async for session in get_async_session():
        yield CRUDOperations(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, graph_store, searcher
    
    await init_db()
    
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
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(video_router)
app.include_router(graph_router)
app.include_router(search_router)
app.include_router(notebook_router)


# --- Background Task ---

async def process_video_task(job_id: str, url: str):
    """Background task to process video with stage tracking."""
    async for session in get_async_session():
        db = CRUDOperations(session)
        try:
            async def update_stage(stage: str):
                await db.update_job_status(job_id, "processing", stage=stage)
                await session.commit()
            
            result = await pipeline.process_url(url, stage_callback=update_stage)
            
            if result.success:
                content = result.processing_result.extracted_content if result.processing_result else None
                
                content_record = await db.create_content(
                    url=url,
                    title=content.title if content else "Unknown",
                    raw_text=content.text if content else "",
                    content_length=len(content.text) if content else 0,
                )
                
                entities_count = 0
                if result.processing_result and result.processing_result.entities:
                    for entity in result.processing_result.entities:
                        await db.create_entity(
                            name=entity.name,
                            entity_type=entity.entity_type,
                            description=entity.description,
                            confidence=entity.confidence,
                        )
                        entities_count += 1
                
                if content_record and result.processing_result and result.processing_result.entities:
                    for entity in result.processing_result.entities:
                        await db.link_content_entity(
                            content_id=content_record.id,
                            entity_id=entity.id if hasattr(entity, 'id') else str(uuid.uuid4()),
                        )
                
                await db.update_job_status(
                    job_id,
                    "completed",
                    content_id=content_record.id if content_record else None,
                    metadata={
                        "title": content.title if content else "Unknown",
                        "entities_count": entities_count,
                        "steps": result.steps if hasattr(result, 'steps') else [],
                    }
                )
            else:
                await db.update_job_status(job_id, "failed", error=result.error)
        except Exception as e:
            await db.update_job_status(job_id, "failed", error=str(e))
        finally:
            await session.commit()


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
    entities = await db.get_content_entities(content_id)
    return {
        "content_id": content_id,
        "entities": [
            {
                "id": e.id,
                "name": e.name,
                "entity_type": e.entity_type_id,
                "description": e.description,
                "confidence": e.confidence,
            }
            for e in entities
        ],
        "total": len(entities),
    }


@app.get("/api/content/{content_id}/steps")
async def get_content_steps(
    content_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get processing steps for content."""
    content = await db.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Get steps from most recent analysis job
    jobs = await db.list_jobs(limit=1)
    steps = []
    for job in jobs:
        if job.content_id == content_id and job.result_metadata:
            steps = job.result_metadata.get("steps", [])
            break
    
    return {
        "content_id": content_id,
        "url": content.url,
        "title": content.title,
        "steps": steps,
        "total_steps": len(steps),
    }
