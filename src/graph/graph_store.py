import asyncio
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import networkx as nx
from openai import AsyncOpenAI

from src.config import get_settings
from src.config.models import CategorizedItem, EnrichedEntity, EntityType, ContentType, ExtractedRelationship
from src.vector import VectorStore
from loguru import logger


settings = get_settings()


@dataclass
class MergeResult:
    new_nodes: int = 0
    updated_nodes: int = 0
    merged_edges: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class GraphStore:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.vector_store = VectorStore()
        self.embedder = None  # Will be set by pipeline
        self.llm_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Similarity thresholds
        self.SAME_ENTITY_THRESHOLD = 0.92
        self.SIMILAR_ENTITY_THRESHOLD = 0.85
        
        # Node types
        self.NODE_TYPES = {
            "entity": "KnowledgeEntity",
            "topic": "Topic",
            "subtopic": "SubTopic",
            "episodic": "EpisodicMemory",
            "source": "SourceDocument"
        }

    def set_embedder(self, embedder):
        self.embedder = embedder

    async def upsert_knowledge(
        self,
        items: List[CategorizedItem],
        relationships: List[ExtractedRelationship] = None,
    ) -> MergeResult:
        """Upsert categorized items into the neural graph."""
        result = MergeResult()
        
        for item in items:
            try:
                merge_result = await self._upsert_item(item)
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
                    self._create_relationship_edge(rel)
                    result.merged_edges += 1
                except Exception as e:
                    logger.warning(f"Failed to create relationship {rel.source}->{rel.target}: {e}")
        
        # Create co-occurrence edges
        co_occur_edges = self._create_cooccurrence_edges(items)
        result.merged_edges += co_occur_edges
        
        logger.info(f"Graph update complete: {result.new_nodes} new, {result.updated_nodes} updated, {result.merged_edges} edges")
        return result

    async def _upsert_item(self, item: CategorizedItem) -> MergeResult:
        """Upsert a single categorized item."""
        result = MergeResult()
        entity = item.entity
        
        # Generate embedding for similarity check
        if self.embedder:
            embedding = await self.embedder.embed_single(
                f"{entity.name} {entity.description}"
            )
        else:
            embedding = [0.0] * settings.OPENAI_EMBEDDING_DIM
        
        # Check for existing similar entities
        similar = self.vector_store.search_similar(
            query_vector=embedding,
            limit=5,
            filter_type="entity",
            score_threshold=self.SIMILAR_ENTITY_THRESHOLD
        )
        
        existing_node_id = None
        
        for match in similar:
            if match["score"] >= self.SAME_ENTITY_THRESHOLD:
                # SAME ENTITY - Update existing
                existing_node_id = match["id"]
                await self._merge_into_existing(existing_node_id, item, match["payload"])
                result.updated_nodes += 1
                break
            elif match["score"] >= self.SIMILAR_ENTITY_THRESHOLD:
                # SIMILAR ENTITY - Create new node with SIMILAR_TO edge
                if existing_node_id is None:
                    existing_node_id = match["id"]
        
        if existing_node_id is None:
            # NEW ENTITY - Create new node
            new_node_id = await self._create_entity_node(item, embedding)
            result.new_nodes += 1
            
            # Create SIMILAR_TO edges if similar entities found
            for match in similar:
                if match["score"] >= self.SIMILAR_ENTITY_THRESHOLD:
                    await self._create_similar_edge(new_node_id, match["id"], match["score"])
                    result.merged_edges += 1
        
        # Ensure topic hierarchy
        await self._ensure_topic_hierarchy(item)
        
        return result

    async def _create_entity_node(self, item: CategorizedItem, embedding: List[float]) -> str:
        """Create a new entity node in both vector store and graph."""
        entity = item.entity
        node_id = f"entity-{entity.name.lower().replace(' ', '-')}-{uuid4().hex[:8]}"
        
        # Store in vector DB
        self.vector_store.client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[{
                "id": node_id,
                "vector": embedding,
                "payload": {
                    "id": node_id,
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
        
        # Add to graph
        self.graph.add_node(
            node_id,
            **{
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
        )
        
        return node_id

    async def _merge_into_existing(self, node_id: str, item: CategorizedItem, existing_payload: Dict):
        """Merge new information into existing entity node."""
        entity = item.entity
        
        # Update graph node
        if self.graph.has_node(node_id):
            node_data = self.graph.nodes[node_id]
            
            # Append description with timestamp
            new_desc = f"\n\n--- UPDATE {datetime.utcnow().isoformat()} ---\n{entity.description}"
            node_data["description"] = node_data.get("description", "") + new_desc
            
            # Merge web_info
            existing_web = node_data.get("web_info", [])
            new_web = entity.web_info
            merged_web = self._merge_web_info(existing_web, new_web)
            node_data["web_info"] = merged_web
            
            # Merge similar_tools
            existing_tools = node_data.get("similar_tools", [])
            new_tools = entity.similar_tools
            merged_tools = self._merge_tools(existing_tools, new_tools)
            node_data["similar_tools"] = merged_tools
            
            # Merge tags
            existing_tags = set(node_data.get("tags", []))
            new_tags = set(item.tags)
            node_data["tags"] = list(existing_tags | new_tags)
            
            # Update metadata
            node_data["version"] = node_data.get("version", 1) + 1
            node_data["updated_at"] = datetime.utcnow().isoformat()
            node_data["confidence"] = max(node_data.get("confidence", 0), entity.confidence)
            
            # Update content_type if more specific
            if item.content_type != ContentType.UNKNOWN:
                node_data["content_type"] = item.content_type.value
        
        # Store episodic memory of this update
        episodic_id = f"episodic-{uuid4().hex[:12]}"
        self.graph.add_node(
            episodic_id,
            source_node=node_id,
            content=entity.description,
            source_url=entity.source_url,
            source_chunk_id=entity.source_chunk_id,
            content_type=item.content_type.value,
            timestamp=datetime.utcnow().isoformat(),
            node_type="episodic"
        )
        self.graph.add_edge(episodic_id, node_id, relation="UPDATES")
        
        # Update vector store
        self.vector_store.client.set_payload(
            collection_name=settings.QDRANT_COLLECTION,
            payload={
                "description": node_data["description"],
                "web_info": merged_web,
                "similar_tools": merged_tools,
                "tags": node_data["tags"],
                "version": node_data["version"],
                "updated_at": node_data["updated_at"],
                "confidence": node_data["confidence"]
            },
            points=[node_id]
        )

    def _merge_web_info(self, existing: List[Dict], new: List[Dict]) -> List[Dict]:
        """Merge web info, deduplicating by URL."""
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
        """Merge similar tools, deduplicating by name."""
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

    async def _create_similar_edge(self, node1: str, node2: str, weight: float):
        """Create SIMILAR_TO edge between nodes."""
        self.graph.add_edge(
            node1, node2,
            relation="SIMILAR_TO",
            weight=weight,
            created_at=datetime.utcnow().isoformat()
        )
        
        # Also add reverse edge for undirected similarity
        self.graph.add_edge(
            node2, node1,
            relation="SIMILAR_TO",
            weight=weight,
            created_at=datetime.utcnow().isoformat()
        )
    
    def _create_relationship_edge(self, rel: ExtractedRelationship):
        """Create a typed relationship edge between two entities."""
        # Find entity nodes by name
        node1_id = None
        node2_id = None
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get("name", "").lower() == rel.source.lower() and data.get("node_type") == "entity":
                node1_id = node_id
            elif data.get("name", "").lower() == rel.target.lower() and data.get("node_type") == "entity":
                node2_id = node_id
        
        if node1_id and node2_id:
            self.graph.add_edge(
                node1_id, node2_id,
                relation=rel.relation_type.upper(),
                description=rel.description,
                confidence=rel.confidence,
                created_at=datetime.utcnow().isoformat()
            )
    
    def _create_cooccurrence_edges(self, items: List[CategorizedItem]) -> int:
        """Create CO_OCCURS_WITH edges for entities mentioned in the same chunk."""
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
            
            # Find node IDs for these entities
            node_ids = {}
            for name in entity_names:
                for node_id, data in self.graph.nodes(data=True):
                    if data.get("name", "").lower() == name.lower() and data.get("node_type") == "entity":
                        node_ids[name] = node_id
                        break
            
            # Create edges between all pairs
            for i in range(len(entity_names)):
                for j in range(i + 1, len(entity_names)):
                    n1 = node_ids.get(entity_names[i])
                    n2 = node_ids.get(entity_names[j])
                    if n1 and n2:
                        self.graph.add_edge(
                            n1, n2,
                            relation="CO_OCCURS_WITH",
                            source_chunk_id=chunk_id,
                            created_at=datetime.utcnow().isoformat()
                        )
                        edge_count += 1
        
        return edge_count

    async def _ensure_topic_hierarchy(self, item: CategorizedItem):
        """Ensure topic and subtopic nodes exist and are connected."""
        topic_name = item.primary_topic.value
        topic_id = f"topic-{topic_name}"
        
        # Create topic node if not exists
        if not self.graph.has_node(topic_id):
            self.graph.add_node(
                topic_id,
                name=topic_name,
                node_type="topic",
                created_at=datetime.utcnow().isoformat()
            )
        
        # Create subtopic nodes
        for subtopic in item.sub_topics:
            subtopic_id = f"subtopic-{topic_name}-{subtopic}"
            
            if not self.graph.has_node(subtopic_id):
                self.graph.add_node(
                    subtopic_id,
                    name=subtopic,
                    parent_topic=topic_name,
                    node_type="subtopic",
                    created_at=datetime.utcnow().isoformat()
                )
            
            # Connect subtopic to topic
            if not self.graph.has_edge(subtopic_id, topic_id):
                self.graph.add_edge(subtopic_id, topic_id, relation="PART_OF")
        
        # Connect entity to subtopic (or topic if no subtopic)
        entity_nodes = [n for n, d in self.graph.nodes(data=True) 
                       if d.get("name") == item.entity.name and d.get("node_type") == "entity"]
        
        for entity_node in entity_nodes:
            target = entity_node
            if item.sub_topics:
                subtopic_id = f"subtopic-{topic_name}-{item.sub_topics[0]}"
                if self.graph.has_node(subtopic_id):
                    target = subtopic_id
            
            if not self.graph.has_edge(entity_node, target):
                self.graph.add_edge(
                    entity_node, target,
                    relation="BELONGS_TO",
                    created_at=datetime.utcnow().isoformat()
                )

    def get_entity(self, name: str) -> Optional[Dict]:
        """Get entity by name."""
        for node_id, data in self.graph.nodes(data=True):
            if data.get("name", "").lower() == name.lower() and data.get("node_type") == "entity":
                return {"id": node_id, **data}
        return None

    def get_related(self, name: str, relation: str = None, limit: int = 10) -> List[Dict]:
        """Get related entities."""
        entity = self.get_entity(name)
        if not entity:
            return []
        
        node_id = entity["id"]
        related = []
        
        for neighbor in self.graph.successors(node_id):
            edge_data = self.graph.get_edge_data(node_id, neighbor)
            for key, edge in edge_data.items():
                if relation is None or edge.get("relation") == relation:
                    neighbor_data = self.graph.nodes[neighbor]
                    related.append({
                        "node_id": neighbor,
                        "relation": edge.get("relation"),
                        "weight": edge.get("weight"),
                        **neighbor_data
                    })
        
        return related[:limit]

    def export_graph(self, format: str = "graphml") -> str:
        """Export graph to file."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{format}', delete=False) as f:
            if format == "graphml":
                nx.write_graphml(self.graph, f.name)
            elif format == "gexf":
                nx.write_gexf(self.graph, f.name)
            elif format == "json":
                data = nx.node_link_data(self.graph)
                json.dump(data, f)
            return f.name

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        node_types = {}
        for _, data in self.graph.nodes(data=True):
            ntype = data.get("node_type", "unknown")
            node_types[ntype] = node_types.get(ntype, 0) + 1
        
        edge_types = {}
        for _, _, data in self.graph.edges(data=True):
            etype = data.get("relation", "unknown")
            edge_types[etype] = edge_types.get(etype, 0) + 1
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
            "density": nx.density(self.graph) if self.graph.number_of_nodes() > 1 else 0
        }


async def consolidate_graph(graph_store: GraphStore):
    """Background consolidation - merge duplicates, prune low utility."""
    logger.info("Starting graph consolidation...")
    
    # Find near-duplicate entities
    entities = [(n, d) for n, d in graph_store.graph.nodes(data=True) 
                if d.get("node_type") == "entity"]
    
    # Cluster by similarity
    clusters = await _find_similar_clusters(entities, threshold=0.9)
    
    for cluster in clusters:
        if len(cluster) > 1:
            await _merge_cluster(graph_store, cluster)
    
    logger.info("Graph consolidation complete")


async def _find_similar_clusters(entities: List[Tuple], threshold: float) -> List[List[str]]:
    """Find clusters of similar entities."""
    # Simplified: compare names
    clusters = []
    used = set()
    
    for node_id, data in entities:
        if node_id in used:
            continue
        
        cluster = [node_id]
        name = data.get("name", "").lower()
        
        for other_id, other_data in entities:
            if other_id in used or other_id == node_id:
                continue
            
            other_name = other_data.get("name", "").lower()
            
            # Simple similarity: Jaccard on words
            words1 = set(name.split())
            words2 = set(other_name.split())
            
            if words1 and words2:
                similarity = len(words1 & words2) / len(words1 | words2)
                if similarity >= threshold:
                    cluster.append(other_id)
                    used.add(other_id)
        
        if len(cluster) > 1:
            clusters.append(cluster)
            used.update(cluster)
    
    return clusters


async def _merge_cluster(graph_store: GraphStore, cluster: List[str]):
    """Merge a cluster of duplicate entities."""
    # Use LLM to consolidate
    nodes_data = [graph_store.graph.nodes[n] for n in cluster]
    
    prompt = f"""
    These appear to be duplicate entities. Create a single consolidated entry:
    
    {json.dumps([{
        "name": d.get("name"),
        "description": d.get("description", "")[:500],
        "tags": d.get("tags", [])
    } for d in nodes_data], indent=2)}
    
    Return JSON: {{"name": "...", "description": "...", "tags": [...]}}
    """
    
    try:
        response = await graph_store.llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        consolidated = json.loads(response.choices[0].message.content)
        
        # Keep first node, update with consolidated data
        primary = cluster[0]
        for node_id in cluster[1:]:
            # Redirect edges to primary
            for pred in list(graph_store.graph.predecessors(node_id)):
                for key, edge in graph_store.graph.get_edge_data(pred, node_id).items():
                    graph_store.graph.add_edge(pred, primary, **edge)
            for succ in list(graph_store.graph.successors(node_id)):
                for key, edge in graph_store.graph.get_edge_data(node_id, succ).items():
                    graph_store.graph.add_edge(primary, succ, **edge)
            
            # Remove duplicate
            graph_store.graph.remove_node(node_id)
        
        # Update primary with consolidated data
        graph_store.graph.nodes[primary].update(consolidated)
        
    except Exception as e:
        logger.error(f"Cluster merge failed: {e}")