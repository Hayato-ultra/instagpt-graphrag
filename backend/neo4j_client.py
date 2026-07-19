import os
import numpy as np
from neo4j import GraphDatabase
from .entity_dedup import deduplicate_entities, normalize_entity

try:
    from sentence_transformers import SentenceTransformer
    _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    _embed_model = None


def _get_embedding(text: str) -> list[float]:
    if not HAS_EMBEDDINGS or not _embed_model:
        return []
    return _embed_model.encode(text).tolist()


class Neo4jPipelineClient:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._ensure_indexes()

    def close(self):
        self.driver.close()

    def _ensure_indexes(self):
        with self.driver.session() as session:
            indexes = [
                "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                "CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)",
                "CREATE INDEX subtopic_name IF NOT EXISTS FOR (s:SubTopic) ON (s.name)",
                "CREATE INDEX hashtag_name IF NOT EXISTS FOR (h:Hashtag) ON (h.name)",
                "CREATE INDEX category_name IF NOT EXISTS FOR (c:Category) ON (c.name)",
                "CREATE INDEX reel_id IF NOT EXISTS FOR (r:Reel) ON (r.id)",
            ]
            for idx in indexes:
                try:
                    session.run(idx)
                except Exception:
                    pass

            if HAS_EMBEDDINGS:
                try:
                    session.run(
                        "CREATE VECTOR INDEX topic_embedding IF NOT EXISTS "
                        "FOR (t:Topic) ON (t.embedding) "
                        "OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}"
                    )
                    session.run(
                        "CREATE VECTOR INDEX entity_embedding IF NOT EXISTS "
                        "FOR (e:Entity) ON (e.embedding) "
                        "OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}"
                    )
                except Exception:
                    pass

    def _link_cross_reel_topics(self, reel_id: str, topic_name: str):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (r1:Reel {id: $reel_id})-[:DISCUSSES]->(t:Topic {name: $topic})
                MATCH (r2:Reel)-[:DISCUSSES]->(t)
                WHERE r2.id <> r1.id
                MERGE (r1)-[:SHARES_TOPIC]->(r2)
                """,
                reel_id=reel_id,
                topic=topic_name,
            )

    def _link_shared_entities(self, reel_id: str):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (r1:Reel {id: $reel_id})-[:MENTIONS]->(e:Entity)
                MATCH (r2:Reel)-[:MENTIONS]->(e)
                WHERE r2.id <> r1.id
                MERGE (r1)-[:SHARES_ENTITY]->(r2)
                """,
                reel_id=reel_id,
            )

    def _create_category_taxonomy(self, reel_id: str, category: str, topic: str):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (c:Category {name: $category})
                WITH c
                MATCH (t:Topic {name: $topic})
                MERGE (c)-[:HAS_TOPIC]->(t)
                """,
                category=category,
                topic=topic,
            )

    def _store_embedding(self, label: str, name: str, description: str):
        if not HAS_EMBEDDINGS:
            return
        embedding = _get_embedding(description or name)
        if not embedding:
            return
        with self.driver.session() as session:
            session.run(
                f"""
                MATCH (n:{label} {{name: $name}})
                SET n.embedding = $embedding
                """,
                name=name,
                embedding=embedding,
            )

    def ingest_full_analysis(self, reel_id: str, url: str, analysis: dict):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (r:Reel {id: $reel_id})
                ON CREATE SET r.url = $url, r.processed_at = datetime()
                SET r.confidence = $confidence,
                    r.sentiment = $sentiment,
                    r.difficulty = $difficulty,
                    r.target_audience = $audience
                """,
                reel_id=reel_id,
                url=url,
                confidence=analysis.get("confidence", 0.5),
                sentiment=analysis.get("overall_sentiment", "neutral"),
                difficulty=analysis.get("difficulty_level", "beginner"),
                audience=analysis.get("target_audience", ""),
            )

            session.run(
                """
                MERGE (r:Reel {id: $reel_id})
                MERGE (t:Theme {name: $theme})
                MERGE (r)-[:HAS_THEME]->(t)
                """,
                reel_id=reel_id,
                theme=analysis.get("theme", "Unknown"),
            )

            topic_name = analysis.get("topic", "Unknown")
            topic_desc = analysis.get("full_description", "")
            category = analysis.get("category", "unknown")

            session.run(
                """
                MERGE (r:Reel {id: $reel_id})
                MERGE (tp:Topic {name: $topic})
                SET tp.description = $description, tp.category = $category
                MERGE (r)-[:DISCUSSES]->(tp)
                """,
                reel_id=reel_id,
                topic=topic_name,
                description=topic_desc,
                category=category,
            )

            self._create_category_taxonomy(reel_id, category, topic_name)
            self._store_embedding("Topic", topic_name, topic_desc)
            self._link_cross_reel_topics(reel_id, topic_name)

            for sub in analysis.get("sub_topics", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (st:SubTopic {name: $sub_topic})
                    MERGE (r)-[:HAS_SUBTOPIC]->(st)
                    WITH st
                    MATCH (tp:Topic {name: $topic})
                    MERGE (st)-[:BELONGS_TO]->(tp)
                    """,
                    reel_id=reel_id,
                    sub_topic=sub,
                    topic=topic_name,
                )

            for i, step in enumerate(analysis.get("steps_or_details", [])):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (s:Step {name: $step})
                    SET s.order = $order
                    MERGE (r)-[:HAS_STEP]->(s)
                    """,
                    reel_id=reel_id,
                    step=step,
                    order=i + 1,
                )

            for item in analysis.get("not_to_do", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (n:Avoid {name: $item})
                    MERGE (r)-[:DO_NOT]->(n)
                    """,
                    reel_id=reel_id,
                    item=item,
                )

            comp = analysis.get("competitor_comparison", "")
            if comp:
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (c:Comparison {name: $comparison})
                    MERGE (r)-[:COMPARES_WITH]->(c)
                    """,
                    reel_id=reel_id,
                    comparison=comp,
                )

            for pro in analysis.get("advantages_disadvantages", {}).get("pros", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (p:Advantage {name: $pro})
                    MERGE (r)-[:HAS_ADVANTAGE]->(p)
                    """,
                    reel_id=reel_id,
                    pro=pro,
                )

            for con in analysis.get("advantages_disadvantages", {}).get("cons", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (c:Disadvantage {name: $con})
                    MERGE (r)-[:HAS_DISADVANTAGE]->(c)
                    """,
                    reel_id=reel_id,
                    con=con,
                )

            for res in analysis.get("mentioned_resources", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (res:Resource {name: $name})
                    SET res.type = $res_type, res.url = $url, res.confidence = $confidence
                    MERGE (r)-[:MENTIONS_RESOURCE]->(res)
                    """,
                    reel_id=reel_id,
                    name=res.get("name", ""),
                    res_type=res.get("type", ""),
                    url=res.get("url", ""),
                    confidence=res.get("confidence", 0.5),
                )

            raw_entities = analysis.get("key_entities", [])
            deduped = deduplicate_entities(raw_entities)
            for entity in deduped:
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (e:Entity {name: $entity})
                    MERGE (r)-[:MENTIONS]->(e)
                    """,
                    reel_id=reel_id,
                    entity=entity,
                )
                self._store_embedding("Entity", entity, entity)

            self._link_shared_entities(reel_id)

            for quote in analysis.get("key_quotes", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    CREATE (q:Quote {text: $quote})
                    MERGE (r)-[:HAS_QUOTE]->(q)
                    """,
                    reel_id=reel_id,
                    quote=quote,
                )

            for action in analysis.get("action_items", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (a:ActionItem {name: $action})
                    MERGE (r)-[:HAS_ACTION]->(a)
                    """,
                    reel_id=reel_id,
                    action=action,
                )

            for tag in analysis.get("generated_hashtags", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (h:Hashtag {name: $tag})
                    MERGE (r)-[:HAS_HASHTAG]->(h)
                    """,
                    reel_id=reel_id,
                    tag=tag,
                )

            for kw in analysis.get("seo_keywords", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (k:Keyword {name: $kw})
                    MERGE (r)-[:HAS_KEYWORD]->(k)
                    """,
                    reel_id=reel_id,
                    kw=kw,
                )

            for moment in analysis.get("key_moments", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    CREATE (m:KeyMoment {hint: $hint, description: $desc, importance: $importance})
                    MERGE (r)-[:HAS_KEY_MOMENT]->(m)
                    """,
                    reel_id=reel_id,
                    hint=moment.get("timestamp_hint", ""),
                    desc=moment.get("description", ""),
                    importance=moment.get("importance", "medium"),
                )

            for hook in analysis.get("engagement_hooks", []):
                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (h:EngagementHook {name: $hook})
                    MERGE (r)-[:HAS_HOOK]->(h)
                    """,
                    reel_id=reel_id,
                    hook=hook,
                )

    def ingest_segments(self, reel_id: str, segments: list[dict]):
        with self.driver.session() as session:
            for seg in segments:
                ts = seg.get("timestamp", 0)
                transcript = seg.get("transcript", "")
                desc = seg.get("full_description", seg.get("description", ""))
                sentiment = seg.get("sentiment", "neutral")
                confidence = seg.get("confidence", 0.5)
                density = seg.get("density_score", 0.0)

                session.run(
                    """
                    MERGE (r:Reel {id: $reel_id})
                    MERGE (f:Frame {timestamp: $timestamp, reel_id: $reel_id})
                    SET f.description = $description,
                        f.transcript = $transcript,
                        f.sentiment = $sentiment,
                        f.confidence = $confidence,
                        f.density_score = $density
                    MERGE (r)-[:HAS_FRAME]->(f)
                    """,
                    reel_id=reel_id,
                    timestamp=ts,
                    description=desc,
                    transcript=transcript,
                    sentiment=sentiment,
                    confidence=confidence,
                    density=density,
                )

                raw_entities = seg.get("key_entities", [])
                deduped = deduplicate_entities(raw_entities)
                for entity in deduped:
                    session.run(
                        """
                        MERGE (f:Frame {timestamp: $timestamp, reel_id: $reel_id})
                        MERGE (e:Entity {name: $entity})
                        MERGE (f)-[:MENTIONS]->(e)
                        """,
                        timestamp=ts,
                        reel_id=reel_id,
                        entity=entity,
                    )

                for sub in seg.get("sub_topics", []):
                    session.run(
                        """
                        MERGE (f:Frame {timestamp: $timestamp, reel_id: $reel_id})
                        MERGE (st:SubTopic {name: $sub})
                        MERGE (f)-[:COVERS]->(st)
                        """,
                        timestamp=ts,
                        reel_id=reel_id,
                        sub=sub,
                    )

                for tag in seg.get("hashtags_in_text", []):
                    session.run(
                        """
                        MERGE (f:Frame {timestamp: $timestamp, reel_id: $reel_id})
                        MERGE (h:Hashtag {name: $tag})
                        MERGE (f)-[:HAS_HASHTAG]->(h)
                        """,
                        timestamp=ts,
                        reel_id=reel_id,
                        tag=tag,
                    )

    def ingest_reel(self, reel_id: str, url: str, analysis_result: dict):
        full = analysis_result.get("full_analysis", {})
        segments = analysis_result.get("segments", [])

        self.ingest_full_analysis(reel_id, url, full)
        self.ingest_segments(reel_id, segments)

    def find_similar_topics(self, query_text: str, limit: int = 5) -> list[dict]:
        if not HAS_EMBEDDINGS:
            return []
        embedding = _get_embedding(query_text)
        if not embedding:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes('topic_embedding', $limit, $embedding)
                YIELD node, score
                RETURN node.name AS topic, node.description AS description,
                       node.category AS category, score
                ORDER BY score DESC
                """,
                limit=limit,
                embedding=embedding,
            )
            return [dict(record) for record in result]

    def find_similar_entities(self, query_text: str, limit: int = 5) -> list[dict]:
        if not HAS_EMBEDDINGS:
            return []
        embedding = _get_embedding(query_text)
        if not embedding:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes('entity_embedding', $limit, $embedding)
                YIELD node, score
                RETURN node.name AS entity, score
                ORDER BY score DESC
                """,
                limit=limit,
                embedding=embedding,
            )
            return [dict(record) for record in result]

    def get_reels_by_category(self, category: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Category {name: $category})-[:HAS_TOPIC]->(t:Topic)<-[:DISCUSSES]-(r:Reel)
                RETURN r.id AS reel_id, r.url AS url, t.name AS topic,
                       r.sentiment AS sentiment, r.confidence AS confidence
                """,
                category=category,
            )
            return [dict(record) for record in result]

    def get_topic_graph(self, topic_name: str) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Topic {name: $topic})
                OPTIONAL MATCH (t)<-[:HAS_TOPIC]-(c:Category)
                OPTIONAL MATCH (t)<-[:BELONGS_TO]-(st:SubTopic)
                OPTIONAL MATCH (t)<-[:DISCUSSES]-(r:Reel)
                OPTIONAL MATCH (r)-[:MENTIONS]->(e:Entity)
                RETURN c.name AS category,
                       collect(DISTINCT st.name) AS subtopics,
                       collect(DISTINCT {id: r.id, url: r.url}) AS reels,
                       collect(DISTINCT e.name) AS entities
                """,
                topic=topic_name,
            )
            record = session.run(
                "MATCH (t:Topic {name: $topic}) RETURN t.description AS desc",
                topic=topic_name,
            ).single()
            data = result.single()
            if not data:
                return {}
            return {
                "topic": topic_name,
                "description": record["desc"] if record else "",
                "category": data["category"],
                "subtopics": data["subtopics"],
                "reels": data["reels"],
                "entities": data["entities"],
            }

    def get_schema(self) -> str:
        return """Graph Schema:
(:Reel {id, url, processed_at, confidence, sentiment, difficulty, target_audience})
  -[:HAS_THEME]->(:Theme {name})
  -[:DISCUSSES]->(:Topic {name, description, category, embedding})
  -[:HAS_SUBTOPIC]->(:SubTopic {name})
  -[:HAS_STEP]->(:Step {name, order})
  -[:DO_NOT]->(:Avoid {name})
  -[:COMPARES_WITH]->(:Comparison {name})
  -[:HAS_ADVANTAGE]->(:Advantage {name})
  -[:HAS_DISADVANTAGE]->(:Disadvantage {name})
  -[:MENTIONS_RESOURCE]->(:Resource {name, type, url, confidence})
  -[:MENTIONS]->(:Entity {name, embedding})
  -[:HAS_FRAME]->(:Frame {timestamp, description, transcript, sentiment, confidence, density_score})
  -[:HAS_QUOTE]->(:Quote {text})
  -[:HAS_ACTION]->(:ActionItem {name})
  -[:HAS_HASHTAG]->(:Hashtag {name})
  -[:HAS_KEYWORD]->(:Keyword {name})
  -[:HAS_KEY_MOMENT]->(:KeyMoment {hint, description, importance})
  -[:HAS_HOOK]->(:EngagementHook {name})
  -[:SHARES_TOPIC]->(:Reel)
  -[:SHARES_ENTITY]->(:Reel)

(:Category {name})-[:HAS_TOPIC]->(:Topic)
(:SubTopic)-[:BELONGS_TO]->(:Topic)
(:Frame)-[:MENTIONS]->(:Entity)
(:Frame)-[:COVERS]->(:SubTopic)
(:Frame)-[:HAS_HASHTAG]->(:Hashtag)

Vector Indexes:
  - topic_embedding on Topic.embedding (384d, cosine)
  - entity_embedding on Entity.embedding (384d, cosine)"""
