import asyncio
import json
import os
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from uuid import uuid4

from neo4j import AsyncGraphDatabase, AsyncDriver

from src.config import get_settings
from src.config.models import CategorizedItem, EnrichedEntity, EntityType, ContentType, ExtractedRelationship
from src.vector import VectorStore
from src.graph.base import GraphStore, MergeResult
from loguru import logger


settings = get_settings()


class Neo4jGraphStore(GraphStore):
    """Neo4j-backed knowledge graph with vector similarity via Qdrant.
    
    Architecture:
    - Neo4j: entity nodes, topic hierarchy, relationships (graph traversal)
    - Qdrant: vector embeddings, semantic similarity search (vector authority)
    - PostgreSQL: application state, sources, content metadata (managed by API layer)
    """
    
    def __init__(self):
        self.driver: Optional[AsyncDriver] = None
        self.vector_store = VectorStore()
        self.embedder = None  # Set by pipeline
        self.llm_client = LLMClient()  # Use unified LLM client with Ollama support
        
        # Similarity thresholds
        self.SAME_ENTITY_THRESHOLD = 0.92
        self.SIMILAR_ENTITY_THRESHOLD = 0.85
        
        # Neo4j connection settings
        self.uri = getattr(settings, 'NEO4J_URI', 'bolt://localhost:7687')
        self.user = getattr(settings, 'NEO4J_USER', 'neo4j')
        self.password = getattr(settings, 'NEO4J_PASSWORD', 'password')
    
    async def connect(self):
        """Initialize Neo4j connection and create constraints/indexes."""
        # Debug: log credentials (masked)
        logger.info(f"--- DEBUG NEO4J CONNECT ---")
        logger.info(f"URI: {self.uri}")
        logger.info(f"USER: {self.user}")
        logger.info(f"PASS LENGTH: {len(self.password)}")
        logger.info(f"PASS PREVIEW: {'*' * max(0, len(self.password) - 4)}{self.password[-4:] if len(self.password) > 4 else ''}")
        logger.info(f"----------------------------")
        
        self.driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )
        
        # Verify connection
        await self.driver.verify_connectivity()
        logger.info("Connected to Neo4j")
        
        # Create constraints and indexes
        await self._create_schema()
    
    async def close(self):
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
    
    async def _create_schema(self):
        """Create constraints and indexes for performance.
        
        Neo4j stores graph structure only. Vectors are in Qdrant.
        """
        queries = [
            # Unique constraints
            "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT source_url IF NOT EXISTS FOR (s:Source) REQUIRE s.url IS UNIQUE",
            
            # Indexes for common queries
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX entity_topic IF NOT EXISTS FOR (e:Entity) ON (e.topic)",
            "CREATE INDEX entity_updated IF NOT EXISTS FOR (e:Entity) ON (e.updated_at)",
            "CREATE INDEX episodic_timestamp IF NOT EXISTS FOR (ep:EpisodicMemory) ON (ep.timestamp)",
            
            # Fulltext search index for entity search
            "CREATE FULLTEXT INDEX entity_search IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.description, e.summary]",
        ]
        
        async with self.driver.session() as session:
            for query in queries:
                try:
                    await session.run(query)
                except Exception as e:
                    logger.warning(f"Schema query failed (may already exist): {e}")
    
    def set_embedder(self, embedder):
        self.embedder = embedder
    
    async def upsert_knowledge(
        self,
        items: List[CategorizedItem],
        relationships: List[ExtractedRelationship] = None,
    ) -> MergeResult:
        """Upsert categorized items and relationships into Neo4j."""
        result = MergeResult()
        
        async with self.driver.session() as session:
            for item in items:
                try:
                    merge_result = await self._upsert_item(session, item)
                    result.new_nodes += merge_result.new_nodes
                    result.updated_nodes += merge_result.updated_nodes
                    result.merged_edges += merge_result.merged_edges
                except Exception as e:
                    error_msg = f"Failed to upsert {item.entity.name}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
            
            # Create relationship edges
            if relationships:
                for rel in relationships:
                    try:
                        await self._create_relationship_edge(session, rel)
                        result.merged_edges += 1
                    except Exception as e:
                        logger.warning(f"Failed to create relationship {rel.source}->{rel.target}: {e}")
            
            # Create co-occurrence edges for entities in same chunk
            co_occur_edges = await self._create_cooccurrence_edges(session, items)
            result.merged_edges += co_occur_edges
        
        logger.info(f"Graph update complete: {result.new_nodes} new, {result.updated_nodes} updated, {result.merged_edges} edges")
        return result
    
    async def _upsert_item(self, session, item: CategorizedItem) -> MergeResult:
        """Upsert a single categorized item.
        
        Deduplication priority:
        1. Exact name match (case-insensitive) + same topic/sub-topic → MERGE
        2. Exact name match + different topic → NEW node (different context)
        3. Embedding similarity >= 0.92 → MERGE
        4. Embedding similarity 0.85-0.92 → NEW node + SIMILAR_TO edge
        5. No match → NEW node
        """
        result = MergeResult()
        entity = item.entity
        topic_name = item.primary_topic.value
        subtopic_name = item.sub_topics[0] if item.sub_topics else None
        
        # Generate embedding for similarity check
        if not self.embedder:
            raise RuntimeError("Embedder not set — cannot generate entity embeddings")
        
        embedding = await self.embedder.embed_single(
            f"{entity.name} {entity.type.value} {entity.description}"
        )
        
        # Priority 1: Exact name match (case-insensitive)
        name_match = await self._find_by_name(session, entity.name)
        if name_match:
            # Entity already exists - always merge into it (unique constraint on name)
            existing_payload = {
                "id": name_match["id"],
                "node_id": name_match["id"],
                "qdrant_id": name_match.get("qdrant_id"),
                "description": name_match.get("description", ""),
            }
            await self._merge_into_existing(session, name_match["id"], item, existing_payload)
            result.updated_nodes += 1
            return result
        
        # Priority 2: Embedding similarity (fuzzy match)
        similar = self.vector_store.search_similar(
            query_vector=embedding,
            limit=5,
            filter_type="entity",
            score_threshold=self.SIMILAR_ENTITY_THRESHOLD
        )
        
        existing_qdrant_id = None
        existing_node_id = None
        
        for match in similar:
            if match["score"] >= self.SAME_ENTITY_THRESHOLD:
                # SAME ENTITY (by embedding) - Update existing
                existing_qdrant_id = match["id"]
                existing_node_id = match["payload"].get("node_id")
                if existing_node_id:
                    await self._merge_into_existing(session, existing_node_id, item, match["payload"])
                    result.updated_nodes += 1
                break
            elif match["score"] >= self.SIMILAR_ENTITY_THRESHOLD:
                # SIMILAR ENTITY - track for edge creation
                if existing_qdrant_id is None:
                    existing_qdrant_id = match["id"]
                    existing_node_id = match["payload"].get("node_id")
        
        if existing_qdrant_id is None:
            # NEW ENTITY - Create new node
            new_node_id = await self._create_entity_node(session, item, embedding)
            result.new_nodes += 1
            
            # Create SIMILAR_TO edges if similar entities found
            for match in similar:
                if match["score"] >= self.SIMILAR_ENTITY_THRESHOLD:
                    similar_node_id = match["payload"].get("node_id")
                    if similar_node_id:
                        await self._create_similar_edge(session, new_node_id, similar_node_id, match["score"])
                        result.merged_edges += 1
        
        # Ensure topic hierarchy
        await self._ensure_topic_hierarchy(session, item)
        
        return result
    
    async def _find_by_name(self, session, name: str) -> Optional[Dict]:
        """Find existing entity by exact name match (case-insensitive).
        
        Returns entity info with topic/subtopic context, or None if not found.
        """
        query = """
        MATCH (e:Entity)
        WHERE toLower(e.name) = toLower($name)
        OPTIONAL MATCH (e)-[:BELONGS_TO]->(t:Topic)
        OPTIONAL MATCH (e)-[:BELONGS_TO]->(s:SubTopic)
        RETURN e.id as id, e.name as name, e.qdrant_id as qdrant_id,
               e.description as description, t.name as topic, s.name as sub_topic
        LIMIT 1
        """
        record = await (await session.run(query, name=name)).single()
        return dict(record) if record else None
    
    async def _create_entity_node(self, session, item: CategorizedItem, embedding: List[float]) -> str:
        """Create a new entity node in Neo4j."""
        entity = item.entity
        node_id = f"entity-{entity.name.lower().replace(' ', '-')}-{uuid4().hex[:8]}"
        qdrant_id = str(uuid4())
        
        # Build properties — vectors live in Qdrant, not Neo4j
        props = {
            "id": node_id,
            "qdrant_id": qdrant_id,
            "name": entity.name,
            "type": entity.type.value,
            "topic": item.primary_topic.value,
            "sub_topic": item.sub_topics[0] if item.sub_topics else None,
            "content_type": item.content_type.value,
            "description": entity.description,
            "summary": item.summary,
            "key_points": json.dumps(item.key_points),
            "web_info": json.dumps(entity.web_info),
            "similar_tools": json.dumps(entity.similar_tools),
            "tags": json.dumps(item.tags),
            "source_url": entity.source_url,
            "source_chunk_id": entity.source_chunk_id,
            "confidence": entity.confidence,
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Remove None values
        props = {k: v for k, v in props.items() if v is not None}
        
        # Create node in Neo4j
        query = """
        CREATE (e:Entity $props)
        RETURN e.id as id
        """
        await session.run(query, props=props)
        
        # Also upsert in Qdrant for vector search (use UUID for Qdrant ID)
        self.vector_store.client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[{
                "id": qdrant_id,
                "vector": embedding,
                "payload": {
                    "id": node_id,
                    "qdrant_id": qdrant_id,
                    "name": entity.name,
                    "type": entity.type.value,
                    "topic": item.primary_topic.value,
                    "sub_topic": item.sub_topics[0] if item.sub_topics else None,
                    "content_type": item.content_type.value,
                    "description": entity.description,
                    "summary": item.summary,
                    "key_points": item.key_points,
                    "web_info": entity.web_info,
                    "similar_tools": entity.similar_tools,
                    "tags": item.tags,
                    "source_url": entity.source_url,
                    "source_chunk_id": entity.source_chunk_id,
                    "confidence": entity.confidence,
                    "version": 1,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "node_type": "entity"
                }
            }]
        )
        
        return node_id
    
    async def _merge_into_existing(self, session, node_id: str, item: CategorizedItem, existing_payload: Dict):
        """Merge new information into existing entity node."""
        entity = item.entity
        
        # Get current node data
        query = """
        MATCH (e:Entity {id: $node_id})
        RETURN e
        """
        record = await session.run(query, node_id=node_id).single()
        
        if record:
            node_data = dict(record["e"])
            qdrant_id = node_data.get("qdrant_id", existing_payload.get("qdrant_id", node_id))
            
            # Merge description with timestamp
            new_desc = f"\n\n--- UPDATE {datetime.utcnow().isoformat()} ---\n{entity.description}"
            merged_desc = node_data.get("description", "") + new_desc
            
            # Merge web_info
            existing_web = json.loads(node_data.get("web_info", "[]"))
            merged_web = self._merge_web_info(existing_web, entity.web_info)
            
            # Merge similar_tools
            existing_tools = json.loads(node_data.get("similar_tools", "[]"))
            merged_tools = self._merge_tools(existing_tools, entity.similar_tools)
            
            # Merge tags
            existing_tags = set(json.loads(node_data.get("tags", "[]")))
            new_tags = set(item.tags)
            merged_tags = list(existing_tags | new_tags)
            
            # Update in Neo4j
            update_props = {
                "description": merged_desc,
                "web_info": json.dumps(merged_web),
                "similar_tools": json.dumps(merged_tools),
                "tags": json.dumps(merged_tags),
                "version": node_data.get("version", 1) + 1,
                "updated_at": datetime.utcnow().isoformat(),
                "confidence": max(node_data.get("confidence", 0), entity.confidence)
            }
            
            if item.content_type != ContentType.UNKNOWN:
                update_props["content_type"] = item.content_type.value
            
            # Update node
            update_query = """
            MATCH (e:Entity {id: $node_id})
            SET e += $props
            """
            await session.run(update_query, node_id=node_id, props=update_props)
            
            # Create episodic memory
            episodic_id = f"episodic-{uuid4().hex[:12]}"
            episodic_props = {
                "id": episodic_id,
                "source_node": node_id,
                "content": entity.description,
                "source_url": entity.source_url,
                "source_chunk_id": entity.source_chunk_id,
                "content_type": item.content_type.value,
                "timestamp": datetime.utcnow().isoformat()
            }
            episodic_query = """
            CREATE (ep:EpisodicMemory $props)
            WITH ep
            MATCH (e:Entity {id: $node_id})
            CREATE (ep)-[:UPDATES]->(e)
            """
            await session.run(episodic_query, props=episodic_props, node_id=node_id)
            
            # Update Qdrant
            self.vector_store.client.set_payload(
                collection_name=settings.QDRANT_COLLECTION,
                payload={
                    "description": merged_desc,
                    "web_info": merged_web,
                    "similar_tools": merged_tools,
                    "tags": merged_tags,
                    "version": update_props["version"],
                    "updated_at": update_props["updated_at"],
                    "confidence": update_props["confidence"]
                },
                points=[qdrant_id]
            )
    
    def _merge_web_info(self, existing: List[Dict], new: List[Dict]) -> List[Dict]:
        seen_urls = set()
        merged = []
        for item in existing + new:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                merged.append(item)
            elif not url:
                merged.append(item)
        return merged
    
    def _merge_tools(self, existing: List[Dict], new: List[Dict]) -> List[Dict]:
        seen_names = set()
        merged = []
        for tool in existing + new:
            name = tool.get("name", "").lower()
            if name and name not in seen_names:
                seen_names.add(name)
                merged.append(tool)
            elif not name:
                merged.append(tool)
        return merged
    
    async def _create_similar_edge(self, session, node1: str, node2: str, weight: float):
        """Create SIMILAR_TO edge between nodes (bidirectional)."""
        query = """
        MATCH (e1:Entity {id: $node1}), (e2:Entity {id: $node2})
        MERGE (e1)-[r:SIMILAR_TO]->(e2)
        SET r.weight = $weight, r.created_at = $created_at
        MERGE (e2)-[r2:SIMILAR_TO]->(e1)
        SET r2.weight = $weight, r2.created_at = $created_at
        """
        await session.run(query, node1=node1, node2=node2, weight=weight, created_at=datetime.utcnow().isoformat())
    
    async def _create_relationship_edge(self, session, rel: ExtractedRelationship):
        """Create a typed relationship edge between two entities."""
        # Map relation_type to a valid Cypher relationship type
        rel_type_map = {
            "USES": "USES",
            "DEPENDS_ON": "DEPENDS_ON",
            "IMPLEMENTS": "IMPLEMENTS",
            "REPLACES": "REPLACES",
            "INTEGRATES_WITH": "INTEGRATES_WITH",
            "PART_OF": "PART_OF",
            "ALTERNATIVE_TO": "ALTERNATIVE_TO",
            "ENABLES": "ENABLES",
            "EVOLVED_FROM": "EVOLVED_FROM",
            "COMPLEMENTS": "COMPLEMENTS",
        }
        rel_type = rel_type_map.get(rel.relation_type.upper(), "RELATED_TO")
        
        query = f"""
        MATCH (e1:Entity {{name: $source}})
        MATCH (e2:Entity {{name: $target}})
        MERGE (e1)-[r:{rel_type}]->(e2)
        SET r.description = $description,
            r.confidence = $confidence,
            r.created_at = $created_at
        """
        await session.run(
            query,
            source=rel.source,
            target=rel.target,
            description=rel.description,
            confidence=rel.confidence,
            created_at=datetime.utcnow().isoformat(),
        )
    
    async def _create_cooccurrence_edges(self, session, items: List[CategorizedItem]) -> int:
        """Create CO_OCCURS_WITH edges for entities mentioned in the same chunk."""
        # Group entities by source chunk
        chunk_entities = {}
        for item in items:
            chunk_id = item.entity.source_chunk_id
            if chunk_id not in chunk_entities:
                chunk_entities[chunk_id] = []
            chunk_entities[chunk_id].append(item.entity.name)
        
        edge_count = 0
        for chunk_id, entity_names in chunk_entities.items():
            if len(entity_names) < 2:
                continue
            
            # Create edges between all pairs in the same chunk
            for i in range(len(entity_names)):
                for j in range(i + 1, len(entity_names)):
                    query = """
                    MATCH (e1:Entity {name: $name1})
                    MATCH (e2:Entity {name: $name2})
                    MERGE (e1)-[r:CO_OCCURS_WITH]-(e2)
                    SET r.source_chunk_id = $chunk_id,
                        r.occurrence_count = COALESCE(r.occurrence_count, 0) + 1,
                        r.updated_at = $updated_at
                    """
                    await session.run(
                        query,
                        name1=entity_names[i],
                        name2=entity_names[j],
                        chunk_id=chunk_id,
                        updated_at=datetime.utcnow().isoformat(),
                    )
                    edge_count += 1
        
        return edge_count
    
    async def _ensure_topic_hierarchy(self, session, item: CategorizedItem):
        """Ensure topic and subtopic nodes exist and are connected."""
        topic_name = item.primary_topic.value
        
        # Create topic node
        topic_query = """
        MERGE (t:Topic {name: $topic_name})
        ON CREATE SET t.created_at = $created_at
        """
        await session.run(topic_query, topic_name=topic_name, created_at=datetime.utcnow().isoformat())
        
        # Create subtopic nodes (scoped to parent topic)
        for subtopic in item.sub_topics:
            subtopic_query = """
            MERGE (s:SubTopic {name: $subtopic, parent_topic: $topic_name})
            ON CREATE SET s.created_at = $created_at
            WITH s
            MATCH (t:Topic {name: $topic_name})
            MERGE (s)-[:PART_OF]->(t)
            """
            await session.run(subtopic_query, subtopic=subtopic, topic_name=topic_name, created_at=datetime.utcnow().isoformat())
        
        # Connect entity to subtopic (or topic)
        entity_query = """
        MATCH (e:Entity {name: $entity_name})
        OPTIONAL MATCH (t:Topic {name: $topic_name})
        OPTIONAL MATCH (s:SubTopic {name: $subtopic, parent_topic: $topic_name})
        FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
            MERGE (e)-[:BELONGS_TO]->(s)
        )
        FOREACH (_ IN CASE WHEN s IS NULL AND t IS NOT NULL THEN [1] ELSE [] END |
            MERGE (e)-[:BELONGS_TO]->(t)
        )
        RETURN 1
        """
        await session.run(entity_query, 
            entity_name=item.entity.name, 
            topic_name=topic_name,
            subtopic=item.sub_topics[0] if item.sub_topics else ""
        )
    
    async def get_entity(self, name: str) -> Optional[Dict]:
        """Get entity by name."""
        query = """
        MATCH (e:Entity {name: $name})
        RETURN e
        """
        async with self.driver.session() as session:
            record = await session.run(query, name=name).single()
            return dict(record["e"]) if record else None
    
    async def get_related(self, name: str, relation: str = None, limit: int = 10) -> List[Dict]:
        """Get related entities."""
        rel_clause = f"WHERE type(r) = '{relation}'" if relation else ""
        
        query = f"""
        MATCH (e:Entity {{name: $name}})-[r]->(related)
        {rel_clause}
        RETURN related, type(r) as relation, r.weight as weight
        LIMIT $limit
        """
        async with self.driver.session() as session:
            records = await session.run(query, name=name, limit=limit).data()
            return [{"node": dict(r["related"]), "relation": r["relation"], "weight": r["weight"]} for r in records]
    
    async def search_entities(self, query_text: str, limit: int = 10) -> List[Dict]:
        """Full-text search on entities."""
        query = """
        CALL db.index.fulltext.queryNodes('entity_search', $query)
        YIELD node, score
        RETURN node, score
        LIMIT $limit
        """
        async with self.driver.session() as session:
            records = await session.run(query, query=query_text, limit=limit).data()
            return [dict(r["node"]) for r in records]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        queries = {
            "total_nodes": "MATCH (n) RETURN count(n) as count",
            "total_edges": "MATCH ()-[r]->() RETURN count(r) as count",
            "node_types": "MATCH (n) RETURN labels(n)[0] as type, count(n) as count",
            "edge_types": "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count",
        }
        
        stats = {}
        async with self.driver.session() as session:
            for key, query in queries.items():
                result = await session.run(query)
                stats[key] = await result.data()
        
        return stats
    
    async def export_graph(self, format: str = "cypher") -> str:
        """Export graph as Cypher statements."""
        query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n, r, m
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            
            if format == "cypher":
                lines = []
                for r in records:
                    node = r["n"]
                    labels = ":".join(node.labels)
                    props = ", ".join(f"{k}: ${k}" for k in node.keys())
                    lines.append(f"CREATE (:{labels} {{{props}}});")
                
                return "\n".join(lines)
            
            return json.dumps(records, default=str)


# Factory function to choose graph store
async def create_graph_store() -> Neo4jGraphStore:
    """Create and connect Neo4j graph store."""
    store = Neo4jGraphStore()
    await store.connect()
    return store