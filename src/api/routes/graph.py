"""Knowledge graph routes."""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.api.routes import get_db
from src.database import CRUDOperations


router = APIRouter(prefix="/api/graph", tags=["graph"])


def _neo4j_to_dict(obj) -> dict:
    """Convert Neo4j Node/Relationship or plain dict to a Python dict."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return {k: obj[k] for k in obj.keys()}
    except Exception:
        return {}


def get_graph_store():
    """Get graph store from app state."""
    from src.api import graph_store
    return graph_store


@router.get("/")
async def get_graph():
    """Get full knowledge graph."""
    store = get_graph_store()
    if not store:
        return {"nodes": [], "edges": []}
    
    query = """
    MATCH (e:Entity)
    OPTIONAL MATCH (e)-[r1]->(t)
    WHERE t:Topic OR t:SubTopic
    OPTIONAL MATCH (e)-[r2]-(other:Entity)
    WHERE other.name <> e.name
    RETURN e, r1, t, r2, other
    LIMIT 500
    """
    
    async with store.driver.session() as session:
        result = await session.run(query)
        records = await result.data()
    
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()
    
    def _add_node(node_dict):
        name = node_dict.get("name", "")
        nid = node_dict.get("id", name)
        if not name or nid in seen_nodes:
            return
        seen_nodes.add(nid)
        nodes.append({
            "id": nid,
            "type": node_dict.get("type", "entity"),
            "label": name,
            "properties": node_dict,
        })
    
    def _add_edge(source_id, target_id, rel_type, edge_id=None):
        eid = edge_id or f"{source_id}--{target_id}--{rel_type}"
        if eid in seen_edges:
            return
        seen_edges.add(eid)
        edges.append({
            "id": eid,
            "source": source_id,
            "target": target_id,
            "type": rel_type,
        })
    
    for r in records:
        try:
            entity = _neo4j_to_dict(r.get("e"))
        except Exception:
            continue
        e_name = entity.get("name", "")
        e_id = entity.get("id", e_name)
        if not e_name:
            continue
        _add_node(entity)
        
        # Entity -> Topic/SubTopic edges
        t = r.get("t")
        if t:
            try:
                topic = _neo4j_to_dict(t)
            except Exception:
                continue
            t_name = topic.get("name", "")
            t_id = f"topic-{t_name}"
            if t_name:
                _add_node({"id": t_id, "type": "topic", "name": t_name, **topic})
                rel_type = "BELONGS_TO"
                if r.get("r1"):
                    try:
                        rel_dict = _neo4j_to_dict(r["r1"])
                        rel_type = rel_dict.get("type", "BELONGS_TO")
                    except Exception:
                        pass
                _add_edge(e_id, t_id, rel_type)
        
        # Entity <-> Entity edges
        other = r.get("other")
        if other:
            try:
                other_dict = _neo4j_to_dict(other)
            except Exception:
                continue
            o_name = other_dict.get("name", "")
            o_id = other_dict.get("id", o_name)
            if o_name and o_name != e_name:
                _add_node(other_dict)
                rel_type = "RELATED_TO"
                if r.get("r2"):
                    try:
                        rel_dict = _neo4j_to_dict(r["r2"])
                        rel_type = rel_dict.get("type", "RELATED_TO")
                    except Exception:
                        pass
                _add_edge(e_id, o_id, rel_type)
    
    return {"nodes": nodes, "edges": edges}


@router.get("/video/{video_id}")
async def get_video_graph(video_id: str):
    """Get graph for a specific video."""
    store = get_graph_store()
    
    query = """
    MATCH (e:Entity)
    WHERE e.source_url CONTAINS $video_id OR e.id CONTAINS $video_id
    OPTIONAL MATCH (e)-[r1]->(t)
    WHERE t:Topic OR t:SubTopic
    OPTIONAL MATCH (e)-[r2]-(other:Entity)
    WHERE other.name <> e.name
    RETURN e, r1, t, r2, other
    LIMIT 500
    """
    
    async with store.driver.session() as session:
        result = await session.run(query, video_id=video_id)
        records = await result.data()
    
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()
    
    def _add_node(node_dict):
        name = node_dict.get("name", "")
        nid = node_dict.get("id", name)
        if not name or nid in seen_nodes:
            return
        seen_nodes.add(nid)
        nodes.append({
            "id": nid,
            "type": node_dict.get("type", "entity"),
            "label": name,
            "properties": node_dict,
        })
    
    def _add_edge(source_id, target_id, rel_type):
        eid = f"{source_id}--{target_id}--{rel_type}"
        if eid in seen_edges:
            return
        seen_edges.add(eid)
        edges.append({
            "id": eid,
            "source": source_id,
            "target": target_id,
            "type": rel_type,
        })
    
    for r in records:
        try:
            entity = _neo4j_to_dict(r.get("e"))
        except Exception:
            continue
        e_name = entity.get("name", "")
        e_id = entity.get("id", e_name)
        if not e_name:
            continue
        _add_node(entity)
        
        t = r.get("t")
        if t:
            try:
                topic = _neo4j_to_dict(t)
            except Exception:
                continue
            t_name = topic.get("name", "")
            t_id = f"topic-{t_name}"
            if t_name:
                _add_node({"id": t_id, "type": "topic", "name": t_name, **topic})
                rel_type = "BELONGS_TO"
                if r.get("r1"):
                    try:
                        rel_dict = _neo4j_to_dict(r["r1"])
                        rel_type = rel_dict.get("type", "BELONGS_TO")
                    except Exception:
                        pass
                _add_edge(e_id, t_id, rel_type)
        
        other = r.get("other")
        if other:
            try:
                other_dict = _neo4j_to_dict(other)
            except Exception:
                continue
            o_name = other_dict.get("name", "")
            o_id = other_dict.get("id", o_name)
            if o_name and o_name != e_name:
                _add_node(other_dict)
                rel_type = "RELATED_TO"
                if r.get("r2"):
                    try:
                        rel_dict = _neo4j_to_dict(r["r2"])
                        rel_type = rel_dict.get("type", "RELATED_TO")
                    except Exception:
                        pass
                _add_edge(e_id, o_id, rel_type)
    
    return {"nodes": nodes, "edges": edges}


@router.get("/node/{node_type}/{node_id}")
async def get_node_detail(node_type: str, node_id: str):
    """Get single node + related nodes."""
    store = get_graph_store()
    
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
    
    entity = _neo4j_to_dict(record["e"])
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


@router.get("/stats")
async def get_graph_stats():
    """Get graph statistics."""
    store = get_graph_store()
    
    stats = await store.get_stats()
    return stats


@router.get("/entity/{entity_name}")
async def get_entity(entity_name: str):
    """Get entity details."""
    store = get_graph_store()
    
    entity = await store.get_entity(entity_name)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/export")
async def export_graph(format: str = "json"):
    """Export graph in various formats."""
    store = get_graph_store()
    
    if format == "graphml":
        content = await store.export_graphml()
        return {"format": "graphml", "content": content}
    elif format == "gexf":
        content = await store.export_gexf()
        return {"format": "gexf", "content": content}
    else:
        content = await store.export_json()
        return {"format": "json", "content": content}


@router.get("/relationships/{entity_name}")
async def get_entity_relationships(entity_name: str):
    """Get relationships for an entity."""
    store = get_graph_store()
    
    related = await store.get_related(entity_name)
    return {"entity": entity_name, "relationships": related}


# --- Edit / Merge / Create custom node ---


class EditNodeRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[str] = None
    tags: Optional[str] = None
    topic: Optional[str] = None
    sub_topic: Optional[str] = None
    content_type: Optional[str] = None
    source_url: Optional[str] = None


@router.put("/node/{node_id}")
async def edit_node(node_id: str, body: EditNodeRequest):
    """Edit a node's properties in Neo4j."""
    store = get_graph_store()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = ", ".join(f"e.{k} = ${k}" for k in updates)
    query = f"""
    MATCH (e:Entity)
    WHERE e.id = $node_id OR e.name = $node_id
    SET {set_clauses}
    RETURN e
    """
    params = {"node_id": node_id, **updates}

    async with store.driver.session() as session:
        result = await session.run(query, **params)
        record = await result.single()

    if not record:
        raise HTTPException(status_code=404, detail="Node not found")

    entity = _neo4j_to_dict(record["e"])
    return {"ok": True, "node": entity}


class MergeNodesRequest(BaseModel):
    source_id: str
    target_id: str
    merged_name: Optional[str] = None
    merged_description: Optional[str] = None


@router.post("/merge")
async def merge_nodes(body: MergeNodesRequest):
    """Merge source node into target node. Transfers relationships, deletes source."""
    store = get_graph_store()

    async with store.driver.session() as session:
        # Find both nodes
        result = await session.run(
            "MATCH (s:Entity) WHERE s.id = $sid OR s.name = $sid RETURN s",
            sid=body.source_id,
        )
        src = await result.single()
        result = await session.run(
            "MATCH (t:Entity) WHERE t.id = $tid OR t.name = $tid RETURN t",
            tid=body.target_id,
        )
        tgt = await result.single()

        if not src or not tgt:
            raise HTTPException(status_code=404, detail="One or both nodes not found")

        src_entity = _neo4j_to_dict(src["s"])
        tgt_entity = _neo4j_to_dict(tgt["t"])

        merged_name = body.merged_name or tgt_entity.get("name", "")
        merged_desc = body.merged_description or tgt_entity.get("description", "")

        # Transfer all relationships from source to target
        await session.run(
            """
            MATCH (s:Entity) WHERE s.id = $sid OR s.name = $sid
            MATCH (t:Entity) WHERE t.id = $tid OR t.name = $tid
            OPTIONAL MATCH (s)-[r]->(other)
            WHERE other <> t
            FOREACH(_ IN CASE WHEN r IS NOT NULL THEN [1] ELSE [] END |
                CREATE (t)-[r2:RELATED_TO]->(other)
                SET r2 += properties(r)
            )
            WITH s, t
            OPTIONAL MATCH (s)<-[r3]-(other2)
            WHERE other2 <> t
            FOREACH(_ IN CASE WHEN r3 IS NOT NULL THEN [1] ELSE [] END |
                CREATE (t)<-[r4:RELATED_TO]-(other2)
                SET r4 += properties(r3)
            )
            WITH s
            DETACH DELETE s
            """,
            sid=body.source_id,
            tid=body.target_id,
        )

        # Update target name/desc if provided
        if merged_name or merged_desc:
            set_parts = []
            params: Dict[str, Any] = {"tid": body.target_id}
            if merged_name:
                set_parts.append("t.name = $name")
                params["name"] = merged_name
            if merged_desc:
                set_parts.append("t.description = $desc")
                params["desc"] = merged_desc
            await session.run(
                f"MATCH (t:Entity) WHERE t.id = $tid OR t.name = $tid SET {', '.join(set_parts)} RETURN t",
                **params,
            )

    return {"ok": True, "merged_into": body.target_id}


class CreateNodeRequest(BaseModel):
    name: str
    type: str = "entity"
    description: str = ""
    summary: str = ""
    topic: str = ""
    sub_topic: str = ""
    tags: str = "[]"
    key_points: str = "[]"
    content_type: str = "custom"
    source_url: str = ""


@router.post("/node")
async def create_node(body: CreateNodeRequest):
    """Create a custom node in Neo4j."""
    store = get_graph_store()
    import uuid
    node_id = f"custom-{body.name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"

    query = """
    CREATE (e:Entity {
        id: $id,
        name: $name,
        type: $type,
        description: $description,
        summary: $summary,
        topic: $topic,
        sub_topic: $sub_topic,
        tags: $tags,
        key_points: $key_points,
        content_type: $content_type,
        source_url: $source_url
    })
    RETURN e
    """

    async with store.driver.session() as session:
        result = await session.run(
            query,
            id=node_id,
            name=body.name,
            type=body.type,
            description=body.description,
            summary=body.summary,
            topic=body.topic,
            sub_topic=body.sub_topic,
            tags=body.tags,
            key_points=body.key_points,
            content_type=body.content_type,
            source_url=body.source_url,
        )
        record = await result.single()

    entity = _neo4j_to_dict(record["e"])
    return {"ok": True, "node": entity}
