import os
import time
import hashlib
from collections import deque
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="InstaGPT GraphRAG API", version="1.0.0")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

from backend.extract import download_reel, extract_audio
from backend.transcribe import transcribe_audio_segments
from backend.video_processing import process_and_deduplicate_video
from backend.analyze import align_and_analyze
from backend.neo4j_client import Neo4jPipelineClient
from backend.query_engine import TextToCypherEngine
from backend.export import GraphExporter

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

processing_jobs = {}
conversation_history = deque(maxlen=20)


class ProcessRequest(BaseModel):
    url: str


class QueryRequest(BaseModel):
    query: str
    context: bool = True


class BatchRequest(BaseModel):
    urls: list[str]


def generate_reel_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def process_reel_background(url: str, job_id: str):
    try:
        processing_jobs[job_id] = {"status": "processing", "url": url, "progress": []}
        reel_id = generate_reel_id(url)

        processing_jobs[job_id]["progress"].append("Downloading video...")
        video_path = download_reel(url)

        processing_jobs[job_id]["progress"].append("Extracting audio...")
        audio_path = extract_audio(video_path)

        processing_jobs[job_id]["progress"].append("Transcribing...")
        segments = transcribe_audio_segments(audio_path)

        processing_jobs[job_id]["progress"].append("Extracting frames...")
        keyframes = process_and_deduplicate_video(video_path)

        processing_jobs[job_id]["progress"].append("Analyzing transcript...")
        result = align_and_analyze(keyframes, segments)

        processing_jobs[job_id]["progress"].append("Ingesting to graph...")
        client = Neo4jPipelineClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        client.ingest_reel(reel_id, url, result)
        client.close()

        processing_jobs[job_id].update({
            "status": "completed",
            "reel_id": reel_id,
            "topic": result.get("full_analysis", {}).get("topic", "Unknown"),
            "category": result.get("full_analysis", {}).get("category", "unknown"),
        })
    except Exception as e:
        processing_jobs[job_id] = {"status": "failed", "error": str(e)}


@app.get("/")
def root():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"message": "InstaGPT GraphRAG API", "version": "1.0.0"}


@app.post("/process")
def process_reel(req: ProcessRequest, background_tasks: BackgroundTasks):
    job_id = hashlib.md5(req.url.encode()).hexdigest()[:12]
    if job_id in processing_jobs and processing_jobs[job_id]["status"] == "processing":
        return {"job_id": job_id, "status": "already_processing"}

    background_tasks.add_task(process_reel_background, req.url, job_id)
    return {"job_id": job_id, "status": "started", "url": req.url}


@app.get("/process/{job_id}")
def get_job_status(job_id: str):
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return processing_jobs[job_id]


@app.post("/query")
def query_reel(req: QueryRequest):
    engine = TextToCypherEngine(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    if req.context and conversation_history:
        context_str = "Previous conversation:\n"
        for q, a in list(conversation_history)[-5:]:
            context_str += f"Q: {q}\nA: {a}\n\n"
        full_query = f"{context_str}Current question: {req.query}"
    else:
        full_query = req.query

    result = engine.query(full_query)
    engine.close()

    conversation_history.append((req.query, result["answer"]))

    return {
        "cypher": result["cypher"],
        "answer": result["answer"],
        "results": result["raw_results"],
    }


@app.get("/reels")
def list_reels():
    client = Neo4jPipelineClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    with client.driver.session() as session:
        result = session.run(
            "MATCH (r:Reel) RETURN r.id AS id, r.url AS url, "
            "r.sentiment AS sentiment, r.confidence AS confidence "
            "ORDER BY r.processed_at DESC"
        )
        reels = [dict(record) for record in result]
    client.close()
    return {"reels": reels, "count": len(reels)}


@app.get("/reels/{reel_id}")
def get_reel(reel_id: str):
    client = Neo4jPipelineClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    with client.driver.session() as session:
        result = session.run(
            """
            MATCH (r:Reel {id: $reel_id})
            OPTIONAL MATCH (r)-[:HAS_THEME]->(t:Theme)
            OPTIONAL MATCH (r)-[:DISCUSSES]->(tp:Topic)
            OPTIONAL MATCH (r)-[:HAS_SUBTOPIC]->(st:SubTopic)
            OPTIONAL MATCH (r)-[:HAS_STEP]->(s:Step)
            OPTIONAL MATCH (r)-[:MENTIONS]->(e:Entity)
            OPTIONAL MATCH (r)-[:HAS_HASHTAG]->(h:Hashtag)
            OPTIONAL MATCH (r)-[:MENTIONS_RESOURCE]->(res:Resource)
            RETURN r.id AS id, r.url AS url, r.sentiment AS sentiment,
                   r.confidence AS confidence, r.difficulty AS difficulty,
                   t.name AS theme, tp.name AS topic, tp.category AS category,
                   collect(DISTINCT st.name) AS subtopics,
                   collect(DISTINCT s.name) AS steps,
                   collect(DISTINCT e.name) AS entities,
                   collect(DISTINCT h.name) AS hashtags,
                   collect(DISTINCT {name: res.name, type: res.type, url: res.url}) AS resources
            """,
            reel_id=reel_id,
        )
        record = result.single()
    client.close()
    if not record:
        raise HTTPException(status_code=404, detail="Reel not found")
    return dict(record)


@app.get("/categories")
def list_categories():
    client = Neo4jPipelineClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    with client.driver.session() as session:
        result = session.run(
            "MATCH (c:Category)-[:HAS_TOPIC]->(t:Topic) "
            "RETURN c.name AS category, collect(t.name) AS topics, count(t) AS topic_count "
            "ORDER BY topic_count DESC"
        )
        categories = [dict(record) for record in result]
    client.close()
    return {"categories": categories}


@app.get("/entities")
def list_entities():
    client = Neo4jPipelineClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    with client.driver.session() as session:
        result = session.run(
            "MATCH (e:Entity) "
            "OPTIONAL MATCH (r:Reel)-[:MENTIONS]->(e) "
            "RETURN e.name AS name, count(r) AS reel_count "
            "ORDER BY reel_count DESC LIMIT 50"
        )
        entities = [dict(record) for record in result]
    client.close()
    return {"entities": entities}


@app.get("/similar")
def find_similar(req: QueryRequest):
    client = Neo4jPipelineClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    similar_topics = client.find_similar_topics(req.query)
    similar_entities = client.find_similar_entities(req.query)
    client.close()
    return {"similar_topics": similar_topics, "similar_entities": similar_entities}


@app.get("/export/{reel_id}/json")
def export_reel_json(reel_id: str):
    exporter = GraphExporter()
    data = exporter.export_reel_json(reel_id)
    exporter.close()
    if not data:
        raise HTTPException(status_code=404, detail="Reel not found")
    return data


@app.get("/export/{reel_id}/csv")
def export_reel_csv(reel_id: str):
    exporter = GraphExporter()
    result = exporter.export_reel_csv(reel_id)
    exporter.close()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/export/full/json")
def export_full_json():
    exporter = GraphExporter()
    data = exporter.export_full_graph_json()
    exporter.close()
    return data


@app.get("/export/full/csv")
def export_full_csv():
    exporter = GraphExporter()
    result = exporter.export_full_graph_csv()
    exporter.close()
    return result


@app.get("/health")
def health_check():
    try:
        client = Neo4jPipelineClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        with client.driver.session() as session:
            session.run("RETURN 1")
        client.close()
        neo4j_status = "connected"
    except Exception as e:
        neo4j_status = f"error: {e}"

    return {
        "status": "healthy",
        "neo4j": neo4j_status,
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
    }
