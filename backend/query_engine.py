import re
import time
from collections import deque
from groq import Groq
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

client = Groq()

conversation_history = deque(maxlen=10)

_rate_last_call = 0.0
RATE_LIMIT_SECONDS = 1.5


def _rate_limit():
    global _rate_last_call
    elapsed = time.time() - _rate_last_call
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _rate_last_call = time.time()

SCHEMA_PROMPT = """You are an expert Neo4j Cypher developer. Translate questions into Cypher queries using ONLY this schema:

(:Reel {id, url, processed_at, confidence, sentiment, difficulty, target_audience})
  -[:HAS_THEME]->(:Theme {name})
  -[:DISCUSSES]->(:Topic {name, description, category})
  -[:HAS_SUBTOPIC]->(:SubTopic {name})
  -[:HAS_STEP]->(:Step {name, order})
  -[:DO_NOT]->(:Avoid {name})
  -[:COMPARES_WITH]->(:Comparison {name})
  -[:HAS_ADVANTAGE]->(:Advantage {name})
  -[:HAS_DISADVANTAGE]->(:Disadvantage {name})
  -[:MENTIONS_RESOURCE]->(:Resource {name, type, url, confidence})
  -[:MENTIONS]->(:Entity {name})
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

Special commands you can use:
- For "similar to X" queries, use: CALL db.index.vector.queryNodes('topic_embedding', 5, $embedding)
- For "same category" queries, match through Category nodes
- For "related reels" queries, use SHARES_TOPIC or SHARES_ENTITY relationships

Question: {user_query}
Cypher output:"""

BLOCKED_KEYWORDS = [
    "DELETE", "DETACH", "REMOVE", "SET n", "CREATE (n",
    "DROP", "MERGE (n) SET", "FOREACH",
]


def _is_safe_cypher(cypher: str) -> bool:
    upper = cypher.upper()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in upper:
            return False
    if upper.strip().startswith("MATCH") and "RETURN" not in upper:
        return False
    return True


class TextToCypherEngine:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )

    def close(self):
        self.driver.close()

    def _generate_cypher(self, user_query: str) -> str:
        _rate_limit()
        context_msgs = []
        for q, a in list(conversation_history)[-3:]:
            context_msgs.append({"role": "user", "content": q})
            context_msgs.append({"role": "assistant", "content": f"Results: {a[:200]}"})

        messages = [
            {"role": "system", "content": "You generate Cypher queries. Return ONLY the Cypher query, no explanations. Only use MATCH and RETURN statements. Use parameters like $param_name for values."},
            *context_msgs,
            {"role": "user", "content": SCHEMA_PROMPT.format(user_query=user_query)},
        ]

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.0,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip().strip("```cypher").strip("```").strip()

    def _execute_cypher(self, cypher: str) -> list[dict]:
        if not _is_safe_cypher(cypher):
            raise ValueError(f"Blocked unsafe Cypher query: {cypher[:100]}")
        with self.driver.session() as session:
            try:
                result = session.run(cypher)
                return [dict(record) for record in result]
            except Exception as e:
                raise ValueError(f"Cypher execution failed: {e}")

    def _synthesize_response(self, user_query: str, query_results: list[dict]) -> str:
        if not query_results:
            return "No results found for your query."

        _rate_limit()
        context_msgs = []
        for q, a in list(conversation_history)[-3:]:
            context_msgs.append({"role": "user", "content": q})
            context_msgs.append({"role": "assistant", "content": a[:300]})

        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer using ONLY the provided data. Be thorough and detailed. Format lists and comparisons clearly."},
            *context_msgs,
            {"role": "user", "content": f"Question: {user_query}\n\nData from graph database:\n{query_results}"},
        ]

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()

    def query(self, user_query: str) -> dict:
        query_lower = user_query.lower()

        if any(kw in query_lower for kw in ["similar", "related", "like"]):
            return self._semantic_query(user_query)

        try:
            cypher = self._generate_cypher(user_query)
        except Exception as e:
            return {"cypher": "", "raw_results": [], "answer": f"Failed to generate query: {e}"}

        try:
            results = self._execute_cypher(cypher)
        except Exception as e:
            return {"cypher": cypher, "raw_results": [], "answer": f"Query failed: {e}"}

        answer = self._synthesize_response(user_query, results)

        conversation_history.append((user_query, answer))

        return {
            "cypher": cypher,
            "raw_results": results,
            "answer": answer,
        }

    def _semantic_query(self, user_query: str) -> dict:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embedding = model.encode(user_query).tolist()
        except ImportError:
            return self.query(user_query)

        cypher = """
        CALL db.index.vector.queryNodes('topic_embedding', 5, $embedding)
        YIELD node, score
        RETURN node.name AS topic, node.description AS description,
               node.category AS category, score
        ORDER BY score DESC
        """

        try:
            with self.driver.session() as session:
                result = session.run(cypher, embedding=embedding)
                results = [dict(record) for record in result]
        except Exception as e:
            results = []

        answer = self._synthesize_response(user_query, results)

        return {
            "cypher": cypher,
            "raw_results": results,
            "answer": answer,
        }
