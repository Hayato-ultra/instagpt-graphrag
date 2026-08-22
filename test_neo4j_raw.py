import asyncio
import sys
sys.path.insert(0, ".")

async def test():
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "instagpt"))
    
    async with driver.session() as session:
        result = await session.run("MATCH (e:Entity) RETURN e LIMIT 1")
        records = await result.data()
        
        r = records[0]
        e = r["e"]
        print(f"type(r): {type(r)}")
        print(f"type(e): {type(e)}")
        print(f"type(e).__mro__: {type(e).__mro__}")
        
        # Check all methods
        for attr in sorted(dir(e)):
            if not attr.startswith('__'):
                val = getattr(e, attr)
                if not callable(val):
                    print(f"  {attr} = {repr(val)[:200]}")
                else:
                    print(f"  {attr}() = callable")
    
    await driver.close()

asyncio.run(test())
