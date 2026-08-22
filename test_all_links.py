import asyncio
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import KnowledgeGraphPipeline


async def process_link(url: str, pipeline: KnowledgeGraphPipeline, output_dir: str, idx: int) -> dict:
    """Process a single link and return results."""
    print(f"\n{'='*60}")
    print(f"  Link {idx}: {url}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = await pipeline.process_url(url)
        elapsed = time.time() - start

        pr = result.processing_result
        entities_count = len(pr.entities) if pr and pr.entities else 0
        relationships_count = len(pr.relationships) if pr and pr.relationships else 0
        steps_count = len(pr.steps) if pr and pr.steps else 0

        print(f"\n  Completed in {elapsed:.1f}s")
        print(f"  Entities: {entities_count}")
        print(f"  Relationships: {relationships_count}")
        print(f"  Steps: {steps_count}")

        if result.markdown_path:
            print(f"  Markdown: {result.markdown_path}")

        if result.error:
            print(f"  Error: {result.error}")

        return {
            "url": url,
            "success": result.success,
            "entities": entities_count,
            "relationships": relationships_count,
            "steps": steps_count,
            "elapsed": elapsed,
            "md_path": str(result.markdown_path) if result.markdown_path else None,
            "error": result.error,
        }
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  FAILED in {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return {
            "url": url,
            "success": False,
            "error": str(e),
            "elapsed": elapsed,
        }


async def main():
    links_file = os.path.join(os.path.dirname(__file__), "links.txt")
    with open(links_file) as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Processing {len(urls)} links from links.txt")

    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()

    output_dir = os.path.join(os.path.dirname(__file__), "outputs", "batch")
    os.makedirs(output_dir, exist_ok=True)

    results = []
    for idx, url in enumerate(urls, 1):
        result = await process_link(url, pipeline, output_dir, idx)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print(f"  BATCH SUMMARY")
    print(f"{'='*60}")

    success = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"  Total: {len(results)}")
    print(f"  Success: {len(success)}")
    print(f"  Failed: {len(failed)}")

    if success:
        total_entities = sum(r["entities"] for r in success)
        total_steps = sum(r["steps"] for r in success)
        total_time = sum(r["elapsed"] for r in success)
        print(f"  Total entities: {total_entities}")
        print(f"  Total steps: {total_steps}")
        print(f"  Total time: {total_time:.1f}s")

    for r in results:
        status = "OK" if r["success"] else "FAIL"
        print(f"  [{status}] {r['url'][:50]}... ({r['elapsed']:.0f}s)")

    # Save summary
    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary saved to {summary_path}")

    await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
