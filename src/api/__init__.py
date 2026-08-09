"""FastAPI backend for InstaGPT GraphRAG."""
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import get_settings
from src.pipeline import KnowledgeGraphPipeline
from src.graph import Neo4jGraphStore
from src.database import CRUDOperations, get_async_session, init_db, close_db


settings = get_settings()

pipeline: Optional[KnowledgeGraphPipeline] = None
graph_store: Optional[Neo4jGraphStore] = None


async def get_db():
    """Dependency to get database session."""
    async for session in get_async_session():
        yield CRUDOperations(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, graph_store
    
    # Initialize database
    await init_db()
    
    # Initialize pipeline and graph store
    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()
    graph_store = pipeline.graph_store
    
    yield
    
    # Cleanup
    if pipeline:
        await pipeline.close()
    await close_db()


app = FastAPI(
    title="InstaGPT GraphRAG API",
    description="URL to Knowledge Graph Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Video Endpoints ---

@app.post("/api/video/analyze")
async def analyze_video(
    request: Dict[str, str],
    background_tasks: BackgroundTasks,
    db: CRUDOperations = Depends(get_db),
):
    """Start analyzing a video URL."""
    url = request.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    # Create analysis job in database
    job = await db.create_analysis_job(url=url)
    
    background_tasks.add_task(process_video_task, job.id, url)
    
    return {
        "analysis_id": job.id,
        "status": "processing",
        "stage": "starting",
    }


async def process_video_task(job_id: str, url: str):
    """Background task to process video with stage tracking."""
    async for session in get_async_session():
        db = CRUDOperations(session)
        try:
            # Stage callback updates job in real-time
            async def update_stage(stage: str):
                await db.update_job_status(job_id, "processing", stage=stage)
                await session.commit()
            
            result = await pipeline.process_url(url, stage_callback=update_stage)
            
            if result.success:
                content = result.processing_result.extracted_content if result.processing_result else None
                
                # Create content record
                content_record = await db.create_content(
                    url=url,
                    title=content.title if content else "Unknown",
                    raw_text=content.text if content else "",
                    content_length=len(content.text) if content else 0,
                )
                
                # Create entities
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
                
                # Link content to entities
                if content_record and result.processing_result and result.processing_result.entities:
                    for entity in result.processing_result.entities:
                        await db.link_content_entity(
                            content_id=content_record.id,
                            entity_id=entity.id if hasattr(entity, 'id') else str(uuid.uuid4()),
                        )
                
                # Update job status
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


@app.get("/api/video/analysis/{analysis_id}")
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


@app.get("/api/video/{content_id}")
async def get_video(
    content_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get video details."""
    content = await db.get_content_by_id(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return {
        "id": content.id,
        "url": content.url,
        "title": content.title,
        "summary": content.summary,
        "entities_count": content.entities_count,
        "created_at": content.created_at.isoformat() if content.created_at else None,
    }


@app.get("/api/video/")
async def list_videos(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: CRUDOperations = Depends(get_db),
):
    """List all processed videos/content."""
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


# --- Graph Endpoints ---

@app.get("/api/graph")
async def get_graph():
    """Get full graph data from Neo4j."""
    try:
        # Get all entities
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[r]->(related:Entity)
        RETURN e as node, collect({target: related.name, relation: type(r), weight: r.weight}) as connections
        LIMIT 200
        """
        async with graph_store.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
        
        nodes = []
        edges = []
        node_ids = set()
        
        for record in records:
            node = record["node"]
            node_id = node.get("id", node.get("name", ""))
            
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "type": "entity",
                    "label": node.get("name", ""),
                    "properties": dict(node),
                })
            
            for conn in record.get("connections", []):
                if conn.get("target"):
                    edges.append({
                        "id": f"{node_id}-{conn['target']}",
                        "source": node_id,
                        "target": conn["target"],
                        "type": conn.get("relation", "related"),
                        "sourceType": "entity",
                        "targetType": "entity",
                        "confidence": conn.get("weight", 1.0),
                    })
        
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}


@app.get("/api/graph/video/{video_id}")
async def get_video_graph(video_id: str):
    """Get graph for specific video/content."""
    try:
        query = """
        MATCH (e:Entity)
        WHERE e.source_url CONTAINS $video_id OR e.id CONTAINS $video_id
        OPTIONAL MATCH (e)-[r]->(related:Entity)
        RETURN e as node, collect({target: related.name, relation: type(r), weight: r.weight}) as connections
        LIMIT 200
        """
        async with graph_store.driver.session() as session:
            result = await session.run(query, video_id=video_id)
            records = await result.data()
        
        nodes = []
        edges = []
        node_ids = set()
        
        for record in records:
            node = record["node"]
            node_id = node.get("id", node.get("name", ""))
            
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "type": "entity",
                    "label": node.get("name", ""),
                    "properties": dict(node),
                })
            
            for conn in record.get("connections", []):
                if conn.get("target"):
                    edges.append({
                        "id": f"{node_id}-{conn['target']}",
                        "source": node_id,
                        "target": conn["target"],
                        "type": conn.get("relation", "related"),
                        "sourceType": "entity",
                        "targetType": "entity",
                        "confidence": conn.get("weight", 1.0),
                    })
        
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}


@app.get("/api/graph/node/{node_type}/{node_id}")
async def get_node_detail(node_type: str, node_id: str):
    """Get node details with related nodes."""
    try:
        # Try to find by name
        entity = await graph_store.get_entity(node_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Node not found")
        
        related = await graph_store.get_related(node_id, limit=20)
        
        return {
            "id": node_id,
            "type": node_type,
            "name": entity.get("name", ""),
            "description": entity.get("description", ""),
            "properties": {k: v for k, v in entity.items() if k not in ("name", "description")},
            "related_nodes": [{"id": r.get("node", {}).get("name", ""), "type": "entity", "relation": r.get("relation", "")} for r in related],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Search Endpoints ---

@app.post("/api/search")
async def search(
    request: Dict[str, Any],
    db: CRUDOperations = Depends(get_db),
):
    """Search entities."""
    query = request.get("query", "")
    
    try:
        # Use Neo4j full-text search
        results = await graph_store.search_entities(query, limit=20)
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


# --- Notebook Endpoints ---

@app.get("/api/notebook")
async def list_notebook(
    db: CRUDOperations = Depends(get_db),
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


@app.get("/api/notebook/{entry_id}")
async def get_notebook_entry(
    entry_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get notebook entry."""
    content = await db.get_content_by_id(entry_id)
    if not content:
        raise HTTPException(status_code=404, detail="Entry not found")
    
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


# --- Statistics Endpoint ---

@app.get("/api/stats")
async def get_stats(db: CRUDOperations = Depends(get_db)):
    """Get database statistics."""
    stats = await db.get_stats()
    return stats


@app.get("/api/content/{content_id}/entities")
async def get_content_entities(
    content_id: str,
    db: CRUDOperations = Depends(get_db),
):
    """Get entities for a specific content."""
    from sqlalchemy import select
    from src.database.models import Entity, ContentEntity
    
    result = await db.session.execute(
        select(Entity)
        .join(ContentEntity, Entity.id == ContentEntity.entity_id)
        .where(ContentEntity.content_id == content_id)
    )
    entities = result.scalars().all()
    
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
    """Get step-by-step guide for specific content."""
    content = await db.get_content_by_id(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Get steps from the latest job for this content
    from sqlalchemy import select
    from src.database.models import AnalysisJob
    
    result = await db.session.execute(
        select(AnalysisJob)
        .where(AnalysisJob.content_id == content_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    
    steps = []
    if job and job.result_metadata:
        steps = job.result_metadata.get("steps", [])
    
    return {
        "content_id": content_id,
        "url": content.url,
        "title": content.title,
        "steps": steps,
        "total_steps": len(steps),
    }
