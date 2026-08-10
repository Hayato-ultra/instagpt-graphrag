import asyncio
import time
from loguru import logger

async def test():
    from src.pipeline import KnowledgeGraphPipeline
    
    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()
    
    start = time.time()
    try:
        result = await pipeline.process_url(
            "https://www.instagram.com/reels/DawnK11ikdr/",
            stage_callback=lambda s: print(f"  Stage: {s} ({time.time()-start:.1f}s)")
        )
        print(f"\nSuccess: {result.success}")
        if result.processing_result:
            pr = result.processing_result
            print(f"Entities: {len(pr.entities) if pr.entities else 0}")
            print(f"Categorized: {len(pr.categorized_items) if pr.categorized_items else 0}")
            print(f"Relationships: {len(pr.relationships) if pr.relationships else 0}")
            print(f"Steps: {len(pr.steps) if pr.steps else 0}")
        if result.error:
            print(f"Error: {result.error}")
        print(f"Total time: {time.time()-start:.1f}s")
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await pipeline.close()

asyncio.run(test())
