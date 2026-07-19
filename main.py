import os
import sys
import shutil
import hashlib
import time
from dotenv import load_dotenv

from backend.extract import download_reel, extract_audio
from backend.transcribe import transcribe_audio_segments
from backend.video_processing import process_and_deduplicate_video
from backend.analyze import align_and_analyze
from backend.neo4j_client import Neo4jPipelineClient
from backend.query_engine import TextToCypherEngine

load_dotenv()

TEMP_DIRS = ["temp_media", "temp_frames"]


def cleanup_temp():
    for d in TEMP_DIRS:
        if os.path.exists(d):
            shutil.rmtree(d)


def generate_reel_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def process_single_reel(url: str, index: int = None, total: int = None):
    prefix = f"[{index}/{total}] " if index else ""
    print(f"\n{'='*60}")
    print(f"{prefix}Processing: {url}")
    print(f"{'='*60}\n")

    reel_id = generate_reel_id(url)

    try:
        print("[1/6] Downloading video...")
        video_path = download_reel(url)
        print(f"  Saved to: {video_path}")

        print("[2/6] Extracting audio stream...")
        audio_path = extract_audio(video_path)
        print(f"  Audio saved to: {audio_path}")

        print("[3/6] Transcribing with timestamp segments...")
        transcript_segments = transcribe_audio_segments(audio_path)
        print(f"  Generated {len(transcript_segments)} transcript segments")

        print("[4/6] Downsampling frames & pHash deduplication...")
        keyframes = process_and_deduplicate_video(video_path)
        print(f"  Retained {len(keyframes)} unique keyframes")

        print("[5/6] Transcript analysis & entity extraction...")
        analysis_result = align_and_analyze(keyframes, transcript_segments)
        full = analysis_result.get("full_analysis", {})
        print(f"  Theme: {full.get('theme', 'N/A')}")
        print(f"  Topic: {full.get('topic', 'N/A')}")
        print(f"  Category: {full.get('category', 'N/A')}")
        print(f"  Sub-topics: {len(full.get('sub_topics', []))}")
        print(f"  Steps: {len(full.get('steps_or_details', []))}")
        print(f"  Resources: {len(full.get('mentioned_resources', []))}")

        print("[6/6] Ingesting into Neo4j...")
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        client = Neo4jPipelineClient(neo4j_uri, neo4j_user, neo4j_password)
        client.ingest_reel(reel_id, url, analysis_result)
        client.close()
        print("  Ingestion complete!")

        print(f"\n{'='*60}")
        print(f"Pipeline finished for reel: {reel_id}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise
    finally:
        print("Cleaning up temp files...")
        cleanup_temp()
        print("Done.\n")

    return reel_id


def process_reel(url: str):
    return process_single_reel(url)


def process_batch(urls: list[str], delay: float = 15.0):
    total = len(urls)
    results = {"success": [], "failed": []}
    print(f"\n{'='*60}")
    print(f"Batch processing {total} reels (delay: {delay}s between)")
    print(f"{'='*60}\n")

    for i, url in enumerate(urls, 1):
        try:
            reel_id = process_single_reel(url, index=i, total=total)
            results["success"].append({"url": url, "reel_id": reel_id})
        except Exception as e:
            results["failed"].append({"url": url, "error": str(e)})
            print(f"  Skipping remaining due to rate limit? Waiting 60s...")
            time.sleep(60)

        if i < total:
            print(f"  Waiting {delay}s before next reel...")
            time.sleep(delay)

    print(f"\n{'='*60}")
    print(f"Batch complete: {len(results['success'])} succeeded, {len(results['failed'])} failed")
    print(f"{'='*60}\n")
    return results


def query_reel(user_query: str):
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    engine = TextToCypherEngine(neo4j_uri, neo4j_user, neo4j_password)
    result = engine.query(user_query)
    engine.close()

    print(f"\nGenerated Cypher:\n{result['cypher']}\n")
    print(f"Answer:\n{result['answer']}\n")

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py process <instagram_reel_url>")
        print("  python main.py process --batch <urls_file.txt>")
        print("  python main.py query \"your question here\"")
        print("  python main.py server")
        sys.exit(1)

    command = sys.argv[1]

    if command == "process":
        if len(sys.argv) < 3:
            print("Error: Please provide an Instagram Reel URL or --batch flag.")
            sys.exit(1)

        if sys.argv[2] == "--batch":
            if len(sys.argv) < 4:
                print("Error: Please provide a text file with URLs.")
                sys.exit(1)
            with open(sys.argv[3]) as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            delay = float(sys.argv[4]) if len(sys.argv) > 5 else 15.0
            process_batch(urls, delay=delay)
        else:
            process_reel(sys.argv[2])

    elif command == "query":
        if len(sys.argv) < 3:
            print("Error: Please provide a query string.")
            sys.exit(1)
        query_reel(sys.argv[2])

    elif command == "server":
        import uvicorn
        print("Starting InstaGPT API server on http://localhost:8000")
        uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
