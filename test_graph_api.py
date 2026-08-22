import asyncio
import sys
sys.path.insert(0, ".")

from src.api import init_db, graph_store
from src.pipeline import KnowledgeGraphPipeline

async def test():
    from src.api import lifespan
    from fastapi import FastAPI
    app = FastAPI()
    async with lifespan(app):
        from src.api import graph_store as gs
        print(f"graph_store type: {type(gs)}")
        print(f"driver type: {type(gs.driver)}")
        
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[r]->(t)
        WHERE t:Topic OR t:SubTopic
        RETURN e, r, t
        LIMIT 200
        """
        
        async with gs.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
        
        print(f"records count: {len(records)}")
        if records:
            r = records[0]
            print(f"type(r): {type(r)}")
            for k, v in r.items():
                print(f"  key={k}, type(v)={type(v)}, value={repr(v)[:100]}")

asyncio.run(test())
