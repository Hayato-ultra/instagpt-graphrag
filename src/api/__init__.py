"""FastAPI backend for InstaGPT GraphRAG."""
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import get_settings
from src.pipeline import KnowledgeGraphPipeline
from src.graph import Neo4jGraphStore


settings = get_settings()

pipeline: Optional[KnowledgeGraphPipeline] = None
graph_store: Optional[Neo4jGraphStore] = None

# In-memory analysis tracking
analyses: Dict[str, Dict[str, Any]] = {}
videos: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, graph_store
    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()
    graph_store = pipeline.graph_store
    yield
    if pipeline:
        await pipeline.close()


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
async def analyze_video(request: Dict[str, str], background_tasks: BackgroundTasks):
    """Start analyzing a video URL."""
    url = request.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    analysis_id = str(uuid.uuid4())
    analyses[analysis_id] = {
        "analysis_id": analysis_id,
        "status": "processing",
        "stage": "starting",
        "url": url,
        "video_id": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    background_tasks.add_task(process_video_task, analysis_id, url)
    
    return {
        "analysis_id": analysis_id,
        "status": "processing",
        "stage": "starting",
    }


async def process_video_task(analysis_id: str, url: str):
    """Background task to process video."""
    try:
        analyses[analysis_id]["stage"] = "extracting"
        result = await pipeline.process_url(url)
        
        if result.success:
            video_id = str(uuid.uuid4())
            videos[video_id] = {
                "id": video_id,
                "url": url,
                "title": result.processing_result.extracted_content.title if result.processing_result else "Unknown",
                "summary": f"Processed {len(result.processing_result.entities) if result.processing_result else 0} entities",
                "entities_count": len(result.processing_result.entities) if result.processing_result else 0,
                "created_at": datetime.utcnow().isoformat(),
            }
            analyses[analysis_id]["status"] = "completed"
            analyses[analysis_id]["video_id"] = video_id
        else:
            analyses[analysis_id]["status"] = "failed"
            analyses[analysis_id]["error"] = result.error
    except Exception as e:
        analyses[analysis_id]["status"] = "failed"
        analyses[analysis_id]["error"] = str(e)


@app.get("/api/video/analysis/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """Get analysis status."""
    if analysis_id not in analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analyses[analysis_id]


@app.get("/api/video/{video_id}")
async def get_video(video_id: str):
    """Get video details."""
    if video_id not in videos:
        raise HTTPException(status_code=404, detail="Video not found")
    return videos[video_id]


@app.get("/api/video/")
async def list_videos():
    """List all processed videos."""
    return list(videos.values())


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
    """Get graph for specific video."""
    return await get_graph()


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
async def search(request: Dict[str, Any]):
    """Search entities."""
    query = request.get("query", "")
    filters = request.get("filters", [])
    
    try:
        # Use Neo4j full-text search
        results = await graph_store.search_entities(query, limit=20)
        return {"results": results[:20], "total": len(results)}
    except Exception:
        # Fallback to simple search
        results = []
        try:
            async with graph_store.driver.session() as session:
                cypher = """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($query)
                   OR toLower(e.description) CONTAINS toLower($query)
                RETURN e
                LIMIT 20
                """
                result = await session.run(cypher, query=query)
                records = await result.data()
                results = [dict(r["e"]) for r in records]
        except Exception:
            pass
        return {"results": results, "total": len(results)}


# --- Notebook Endpoints ---

@app.get("/api/notebook")
async def list_notebook():
    """List notebook entries."""
    entries = []
    for video_id, video in videos.items():
        entries.append({
            "id": video_id,
            "video_id": video_id,
            "title": video.get("title", ""),
            "summary": video.get("summary", ""),
            "ai_notes": "",
            "links": "",
            "tags": "",
            "created_at": video.get("created_at", ""),
        })
    return {"entries": entries, "total": len(entries)}


@app.get("/api/notebook/{entry_id}")
async def get_notebook_entry(entry_id: str):
    """Get notebook entry."""
    if entry_id not in videos:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    video = videos[entry_id]
    return {
        "id": entry_id,
        "video_id": entry_id,
        "title": video.get("title", ""),
        "summary": video.get("summary", ""),
        "ai_notes": "",
        "links": "",
        "tags": "",
        "created_at": video.get("created_at", ""),
    }
