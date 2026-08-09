"""Knowledge graph routes."""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from src.database import CRUDOperations, get_async_session


router = APIRouter(prefix="/api/graph", tags=["graph"])


def get_graph_store():
    """Get graph store from app state."""
    from src.api import graph_store
    return graph_store


@router.get("/")
async def get_graph():
    """Get full knowledge graph."""
    store = get_graph_store()
    
    query = """
    MATCH (e:Entity)
    OPTIONAL MATCH (e)-[r]->(t)
    WHERE t:Topic OR t:SubTopic
    RETURN e, r, t
    LIMIT 200
    """
    
    async with store.driver.session() as session:
        result = await session.run(query)
        records = await result.data()
    
    nodes = []
    edges = []
    seen_nodes = set()
    
    for r in records:
        entity = dict(r["e"])
        if entity["name"] not in seen_nodes:
            seen_nodes.add(entity["name"])
            nodes.append({
                "id": entity.get("id", entity["name"]),
                "type": entity.get("type", "entity"),
                "label": entity["name"],
                "properties": entity,
            })
        
        if r.get("t"):
            topic = dict(r["t"])
            topic_name = topic.get("name", "")
            if topic_name and topic_name not in seen_nodes:
                seen_nodes.add(topic_name)
                nodes.append({
                    "id": f"topic-{topic_name}",
                    "type": "topic",
                    "label": topic_name,
                    "properties": topic,
                })
            
            if r.get("r"):
                rel = dict(r["r"])
                edges.append({
                    "id": f"{entity['name']}-{topic_name}",
                    "source": entity.get("id", entity["name"]),
                    "target": f"topic-{topic_name}",
                    "type": rel.get("type", "BELONGS_TO"),
                    "sourceType": "entity",
                    "targetType": "topic",
                    "confidence": 1.0,
                })
    
    return {"nodes": nodes, "edges": edges}


@router.get("/video/{video_id}")
async def get_video_graph(video_id: str):
    """Get graph for a specific video."""
    store = get_graph_store()
    
    query = """
    MATCH (e:Entity)
    WHERE e.source_url CONTAINS $video_id OR e.id CONTAINS $video_id
    OPTIONAL MATCH (e)-[r]->(t)
    WHERE t:Topic OR t:SubTopic
    RETURN e, r, t
    """
    
    async with store.driver.session() as session:
        result = await session.run(query, video_id=video_id)
        records = await result.data()
    
    nodes = []
    edges = []
    seen_nodes = set()
    
    for r in records:
        entity = dict(r["e"])
        if entity["name"] not in seen_nodes:
            seen_nodes.add(entity["name"])
            nodes.append({
                "id": entity.get("id", entity["name"]),
                "type": entity.get("type", "entity"),
                "label": entity["name"],
                "properties": entity,
            })
    
    return {"nodes": nodes, "edges": edges}


@router.get("/node/{node_type}/{node_id}")
async def get_node_detail(node_type: str, node_id: str):
    """Get single node + related nodes."""
    store = get_graph_store()
    
    # Get the node
    query = """
    MATCH (e:Entity)
    WHERE e.id = $node_id OR e.name = $node_id
    RETURN e
    """
    
    async with store.driver.session() as session:
        result = await session.run(query, node_id=node_id)
        record = await result.single()
    
    if not record:
        raise HTTPException(status_code=404, detail="Node not found")
    
    entity = dict(record["e"])
    
    # Get related nodes
    related = await store.get_related(entity["name"], limit=20)
    
    return {
        "id": entity.get("id", entity["name"]),
        "type": entity.get("type", "entity"),
        "name": entity["name"],
        "description": entity.get("description", ""),
        "properties": entity,
        "related_nodes": [
            {
                "id": r.get("id", r.get("name", "")),
                "type": r.get("type", "entity"),
                "relation": "RELATED_TO",
            }
            for r in related
        ],
    }
