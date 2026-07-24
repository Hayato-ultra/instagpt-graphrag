from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import get_settings
from src.pipeline import KnowledgeGraphPipeline
from src.graph_store import GraphStore
from loguru import logger

settings = get_settings()

app = FastAPI(title="InstaGPT GraphRAG", version="0.1.0")

# Global pipeline instance
pipeline: Optional[KnowledgeGraphPipeline] = None

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

# Job tracking
jobs: Dict[str, Dict[str, Any]] = {}


class ProcessRequest(BaseModel):
    urls: List[HttpUrl]
    max_concurrent: int = 3


class SearchRequest(BaseModel):
    query: str
    topic: Optional[str] = None
    limit: int = 10


class EntityRequest(BaseModel):
    name: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, running, completed, failed
    progress: int
    total_urls: int
    completed_urls: int
    results: List[Dict[str, Any]]
    errors: List[str]
    created_at: datetime
    completed_at: Optional[datetime] = None


@app.on_event("startup")
async def startup_event():
    global pipeline
    # Debug: log settings
    logger.info("--- DEBUG SETTINGS ---")
    logger.info(f"NEO4J_URI: {settings.NEO4J_URI}")
    logger.info(f"NEO4J_USER: {settings.NEO4J_USER}")
    logger.info(f"NEO4J_PASSWORD length: {len(settings.NEO4J_PASSWORD)}")
    logger.info(f"QDRANT_URL: {settings.QDRANT_URL}")
    logger.info(f"OPENAI_API_KEY length: {len(settings.OPENAI_API_KEY)}")
    logger.info(f"----------------------------")
    
    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    if pipeline:
        await pipeline.close()


# WebSocket for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)


async def broadcast_update(message: Dict[str, Any]):
    """Broadcast update to all connected WebSocket clients."""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass


# Serve static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ============ API Routes ============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse("""
    <html><body><h1>InstaGPT GraphRAG</h1>
    <p>Frontend not built yet. Run <code>python build_frontend.py</code> to generate it.</p>
    </body></html>
    """)


@app.post("/api/process", response_model=JobStatus)
async def process_urls(request: ProcessRequest, background_tasks: BackgroundTasks):
    """Start processing URLs in background."""
    job_id = str(uuid.uuid4())[:8]
    
    job = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "total_urls": len(request.urls),
        "completed_urls": 0,
        "results": [],
        "errors": [],
        "created_at": datetime.utcnow(),
        "completed_at": None
    }
    jobs[job_id] = job
    
    background_tasks.add_task(
        process_job_background, 
        job_id, 
        [str(u) for u in request.urls], 
        request.max_concurrent
    )
    
    return JobStatus(**job)


async def process_job_background(job_id: str, urls: List[str], max_concurrent: int):
    """Background task to process URLs."""
    job = jobs[job_id]
    job["status"] = "running"
    
    await broadcast_update({"type": "job_status", "job": job})
    
    try:
        results = await pipeline.process_batch(urls, max_concurrent)
        
        for i, result in enumerate(results):
            job["completed_urls"] = i + 1
            job["progress"] = int((i + 1) / len(urls) * 100)
            
            if result.success:
                job["results"].append({
                    "url": result.url,
                    "entities": len(result.processing_result.entities),
                    "categorized": len(result.processing_result.categorized_items),
                    "markdown": result.markdown_path,
                    "json": result.json_path,
                    "graph_stats": result.graph_stats
                })
            else:
                job["errors"].append(f"{result.url}: {result.error}")
            
            await broadcast_update({"type": "job_progress", "job": job})
        
        job["status"] = "completed"
        job["completed_at"] = datetime.now(timezone.utc)
        
    except Exception as e:
        job["status"] = "failed"
        job["errors"].append(str(e))
    
    await broadcast_update({"type": "job_status", "job": job})


@app.get("/api/jobs", response_model=List[JobStatus])
async def list_jobs():
    """List all jobs."""
    return [JobStatus(**j) for j in jobs.values()]


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    """Get job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**jobs[job_id])


@app.post("/api/search")
async def search_entities(request: SearchRequest):
    """Search the knowledge graph."""
    # Use graph store directly for search
    graph = GraphStore()
    
    # Simple search implementation
    results = []
    for node_id, data in graph.graph.nodes(data=True):
        if data.get("node_type") == "entity":
            name = data.get("name", "").lower()
            desc = data.get("description", "").lower()
            tags = " ".join(data.get("tags", [])).lower()
            
            if request.query.lower() in name or request.query.lower() in desc or request.query.lower() in tags:
                if request.topic is None or data.get("topic") == request.topic:
                    results.append({
                        "id": node_id,
                        "name": data.get("name"),
                        "type": data.get("type"),
                        "topic": data.get("topic"),
                        "description": data.get("description", "")[:200],
                        "tags": data.get("tags", [])[:5]
                    })
    
    return {"results": results[:request.limit], "total": len(results)}


@app.post("/api/entity")
async def get_entity(request: EntityRequest):
    """Get entity details."""
    graph = GraphStore()
    entity = graph.get_entity(request.name)
    
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    related = graph.get_related(request.name, limit=10)
    
    return {
        "entity": entity,
        "related": related
    }


@app.get("/api/graph/stats")
async def graph_stats():
    """Get graph statistics."""
    graph = GraphStore()
    return graph.get_stats()


@app.get("/api/graph/export")
async def export_graph(format: str = "graphml"):
    """Export graph."""
    graph = GraphStore()
    filepath = graph.export_graph(format)
    return FileResponse(filepath, filename=f"knowledge_graph.{format}")


@app.get("/api/outputs")
async def list_outputs():
    """List generated output files."""
    output_dir = Path(settings.OUTPUT_DIR)
    files = []
    if output_dir.exists():
        for f in output_dir.glob("*.md"):
            files.append({"name": f.name, "path": str(f), "type": "markdown"})
        for f in output_dir.glob("*.json"):
            files.append({"name": f.name, "path": str(f), "type": "json"})
    return {"files": files}


@app.get("/api/outputs/{filename}")
async def get_output(filename: str):
    """Get output file content."""
    filepath = Path(settings.OUTPUT_DIR) / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)


# ============ Run ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)