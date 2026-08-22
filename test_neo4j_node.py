import asyncio
from src.pipeline import KnowledgeGraphPipeline

async def test():
    pipeline = KnowledgeGraphPipeline()
    await pipeline.initialize()
    store = pipeline.graph_store
    async with store.driver.session() as session:
        result = await session.run("MATCH (e:Entity) RETURN e LIMIT 1")
        records = await result.data()
        r = records[0]
        e = r["e"]
        print(f"type(r): {type(r)}")
        print(f"type(e): {type(e)}")
        print(f"dir(e): {[x for x in dir(e) if not x.startswith('_')]}")
        # Try various conversion methods
        try:
            print(f"dict(e): {dict(e)}")
        except Exception as ex:
            print(f"dict(e) failed: {ex}")
        try:
            print(f"dict(e.items()): {dict(e.items())}")
        except Exception as ex:
            print(f"dict(e.items()) failed: {ex}")
        try:
            print(f"dict(e._properties): {dict(e._properties)}")
        except Exception as ex:
            print(f"dict(e._properties) failed: {ex}")
        try:
            print(f"e._asdict(): {e._asdict()}")
        except Exception as ex:
            print(f"e._asdict() failed: {ex}")
        try:
            print(f"dict(e): {dict(e)}")
        except Exception as ex:
            print(f"dict(e) failed: {ex}")
    await pipeline.close()

asyncio.run(test())
