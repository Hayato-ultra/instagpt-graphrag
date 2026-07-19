# Implementation Plan: Target Multimodal Video & GraphRAG Pipeline
**System Architecture, Multimodal Extraction, Temporal Alignment, and Neo4j GraphRAG Integration**

---

## 1. Vision & Architecture Overview
This document maps out the system architecture and implementation path to evolve **InstaGPT / ReelMind** from a text-and-audio application into a high-precision, multimodal video-intelligence engine. 

By upgrading the current pipeline, the platform will process Instagram Reels (`.mp4`), run temporal sub-sampling, strip redundant visual frames with perceptual hashing, align keyframes with timestamped Whisper transcriptions, run visual-text grounding with a Vision-Language Model (VLM), and ingest the structured facts directly into a **Neo4j Graph Database**. 

This transitions the querying system from a fuzzy keyword matching tool into an absolute, deterministic **GraphRAG Engine** capable of Text-to-Cypher execution.

---

## 2. Target Pipeline Architecture

```
                       [ Instagram Reel (.mp4) ]
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
              [ Audio Stream ]            [ Video Stream ]
                     │                           │
         [ Whisper / faster-whisper ]     [ CV2 Downsampler ]
          (Word-level Timestamps)          (2 FPS Frame Grab)
                     │                           │
                     ▼                           ▼
            [ Text Transcript ]           [ Raw Frame Array ]
            (Segment Timestamps)                 │
                     │                           ▼
                     │                 [ ImageHash Filtering ]
                     │                 (pHash Deduplication)
                     │                           │
                     │                           ▼
                     │                  [ Unique Keyframes ]
                     │                           │
                     └─────────────┬─────────────┘
                                   ▼
                       [ Temporal Aligner & VLM ]
                     (GPT-4o / Gemini Flash Grounding)
                                   │
                                   ▼
                         [ Structured Facts ]
                       (Standardized JSON output)
                                   │
                                   ▼
                        [ Neo4j Graph Database ]
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
        [ User Query ] ──► [ LLM Text-to-Cypher ] ──► [ Exact Matches ]
```

---

## 3. Detailed Component Technical Specifications

### Module A: Video Capture & Dual Extraction (`backend/extract.py`)
Modify `extract.py` to preserve both high-fidelity video track data and the clean audio track from the incoming URL payload.
*   **Technology**: `yt-dlp` for video retrieval, `ffmpeg-python` for stream isolation.
*   **Operational Rules**: Download the reel stream as an `.mp4` container. Extract the mono audio channel into a `.wav` file at 16,000Hz.

### Module B: Timestamp-Segment ASR (`backend/transcribe.py`)
Current transcription processes audio blocks as a single paragraph. We must extract temporal timestamps for word groups.
*   **Technology**: `faster-whisper` using CTC (Connectionist Temporal Classification) alignment.
*   **Output Structure**: A list of structured dictionaries tracking start and end bounds:
    ```json
    [
      {"start": 0.0, "end": 2.15, "text": "Welcome to our Python demonstration."},
      {"start": 2.15, "end": 5.40, "text": "Today we're building a graph network."}
    ]
    ```

### Module C: Video Downsampling & pHash Deduplication (`backend/video_processing.py`)
To prevent redundant LLM usage and avoid indexing duplicate frames, we will aggressively filter our video stream.
*   **Phase 1 (Downsampling)**: Use OpenCV to inspect the video properties and capture frames at a target rate of **2 frames per second (FPS)**, bypassing standard 30/60 FPS limits.
*   **Phase 2 (Deduplication)**: Calculate a 64-bit hexadecimal **Perceptual Hash (pHash)** using `ImageHash` for each captured frame. Compute the Hamming distance between the hashes of consecutive frames. If the Hamming distance is less than or equal to a threshold of **10**, discard the current frame as a duplicate.

### Module D: Multimodal Grounding & Entity Parsing (`backend/analyze.py`)
*   **Alignment Logic**: For each unique keyframe, retrieve its exact time-marker. Query the ASR segments to isolate the specific sentence spoken during that window.
*   **Vision-Language Model (VLM)**: Package the base64-encoded image frame alongside its corresponding spoken audio segment. Send this payload to GPT-4o-mini or Gemini 2.5 Flash, requesting a structured analysis of the scene.
*   **Required Structured VLM JSON Output Schema**:
    ```json
    {
      "timestamp": 4.5,
      "topic": "Python Programming",
      "description": "The presenter types an asynchronous function into the code editor.",
      "entities": ["FastAPI", "Python", "Asynchronous Programming", "Uvicorn"],
      "code_snippet": "async def start_server():"
    }
    ```

### Module E: Graph DB Ingestion (`backend/neo4j_client.py`)
Write a dedicated connector to ingest these structured visual-audio snapshots into Neo4j using optimized Cypher queries.
*   **Graph Schema Definition**:
    ```
    (:Reel {id: ID, url: STR}) ──[:HAS_FRAME]──► (:Frame {timestamp: FLOAT, desc: STR, transcript: STR})
                                                     ├──[:DEPICTS]──► (:Entity {name: STR})
                                                     └──[:DISCUSSES]──► (:Topic {name: STR})
    ```
*   **Ingestion Query**:
    ```cypher
    MERGE (r:Reel {id: $reel_id})
    ON CREATE SET r.url = $url, r.processed_at = timestamp()
    
    CREATE (f:Frame {
        timestamp: $timestamp, 
        description: $description, 
        transcript: $transcript, 
        code_snippet: $code_snippet
    })
    CREATE (r)-[:HAS_FRAME]->(f)
    
    WITH f
    UNWIND $entities AS entityName
    MERGE (e:Entity {name: entityName})
    CREATE (f)-[:DEPICTS]->(e)
    
    WITH f
    MERGE (t:Topic {name: $topic})
    CREATE (f)-[:DISCUSSES]->(t)
    ```

---

## 4. Query Engine & GraphRAG Pipeline

Standard vector-based searches often fail to provide exact, factual answers. To ensure absolute precision, we utilize a **Text-to-Cypher** querying pipeline:

```
                  [ Natural Language User Query ]
                  ("Show me the code at 4.5 seconds")
                                 │
                                 ▼
                     [ LLM Cypher Generator ]
                (Injected with DB Schema Metadata)
                                 │
                                 ▼
                      [ Executable Cypher ]
            ("MATCH (f:Frame {timestamp: 4.5}) RETURN f...")
                                 │
                                 ▼
                       [ Neo4j Engine Run ]
                                 │
                                 ▼
                    [ Factual Node Attributes ]
             (No hallucinations / strictly grounded)
                                 │
                                 ▼
                     [ LLM Response Synthesizer ]
```

### Prompt for Text-to-Cypher Generation
```text
You are an expert Neo4j Cypher developer. Your job is to translate human questions into clean Cypher queries based ONLY on the following schema:
- (:Reel {id})-[:HAS_FRAME]->(:Frame {timestamp, description, transcript, code_snippet})
- (:Frame)-[:DEPICTS]->(:Entity {name})
- (:Frame)-[:DISCUSSES]->(:Topic {name})

Question: {user_query}
Cypher output:
```

---

## 5. Development Code Snippets

### OpenCV + ImageHash Filtering Script
```python
import cv2
import os
from PIL import Image
import imagehash

def process_and_deduplicate_video(video_path: str, fps_target: int = 2, threshold: int = 10):
    cap = cv2.VideoCapture(video_path)
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = max(1, int(original_fps / fps_target))
    
    unique_keyframes = []
    previous_hash = None
    frame_idx = 0
    
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break
            
        if frame_idx % frame_interval == 0:
            timestamp = round(frame_idx / original_fps, 2)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            current_hash = imagehash.phash(pil_image)
            
            if previous_hash is None or (current_hash - previous_hash) > threshold:
                frame_path = f"temp_frames/frame_{timestamp}.jpg"
                cv2.imwrite(frame_path, frame)
                unique_keyframes.append({
                    "timestamp": timestamp,
                    "filepath": frame_path,
                    "hash": current_hash
                })
                previous_hash = current_hash
                
        frame_idx += 1
    cap.release()
    return unique_keyframes
```

### Complete Pipeline Integration Script
```python
import os
from neo4j import GraphDatabase

class Neo4jPipelineClient:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        self.driver.close()
        
    def ingest_frame_data(self, reel_id, url, frame_data):
        query = """
        MERGE (r:Reel {id: $reel_id})
        ON CREATE SET r.url = $url
        
        CREATE (f:Frame {
            timestamp: $timestamp, 
            description: $description, 
            transcript: $transcript, 
            code_snippet: $code_snippet
        })
        CREATE (r)-[:HAS_FRAME]->(f)
        
        WITH f
        UNWIND $entities AS entity_name
        MERGE (e:Entity {name: entity_name})
        CREATE (f)-[:DEPICTS]->(e)
        
        WITH f
        MERGE (t:Topic {name: $topic})
        CREATE (f)-[:DISCUSSES]->(t)
        """
        with self.driver.session() as session:
            session.run(
                query,
                reel_id=reel_id,
                url=url,
                timestamp=frame_data["timestamp"],
                description=frame_data["description"],
                transcript=frame_data["transcript"],
                code_snippet=frame_data.get("code_snippet", ""),
                entities=frame_data["entities"],
                topic=frame_data["topic"]
            )
```
