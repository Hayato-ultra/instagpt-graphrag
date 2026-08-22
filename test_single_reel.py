import asyncio
import time
import requests
from pathlib import Path

URL = "https://www.instagram.com/reels/Dbn6ElTvw_W/"


async def run_pipeline(url):
    """Run the full pipeline on a single reel."""
    from src.pipeline import KnowledgeGraphPipeline

    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()

    start = time.time()
    try:
        result = await pipeline.process_url(url)
        elapsed = time.time() - start
        print(f"\nPipeline completed in {elapsed:.1f}s")
        print(f"Success: {result.success}")

        if result.processing_result:
            pr = result.processing_result
            print(f"Entities: {len(pr.entities) if pr.entities else 0}")
            print(f"Categorized: {len(pr.categorized_items) if pr.categorized_items else 0}")
            print(f"Relationships: {len(pr.relationships) if pr.relationships else 0}")
            print(f"Steps: {len(pr.steps) if pr.steps else 0}")

            if pr.steps:
                print(f"\n--- Steps ---")
                for i, step in enumerate(pr.steps, 1):
                    print(f"{i}. {step}")

            if pr.categorized_items:
                print(f"\n--- Categorized items ---")
                for item in pr.categorized_items:
                    print(f"\n{item.entity.name} ({item.entity.type.value})")
                    print(f"  Summary: {item.summary[:300]}")
                    print(f"  Key points: {item.key_points[:3]}")

            if pr.relationships:
                print(f"\n--- Relationships ---")
                for rel in pr.relationships:
                    print(f"  {rel.source} --[{rel.relation_type}]--> {rel.target}: {rel.description[:100]}")

        if result.error:
            print(f"Error: {result.error}")

        if result.markdown_path:
            print(f"\nMarkdown: {result.markdown_path}")

        return result
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await pipeline.close()


async def main():
    print(f"Testing URL: {URL}")
    print("=" * 60)
    result = await run_pipeline(URL)


if __name__ == "__main__":
    asyncio.run(main())
