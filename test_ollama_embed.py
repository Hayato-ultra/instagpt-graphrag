import asyncio
import sys
sys.path.insert(0, '.')

async def test():
    from src.vector.vector_store import Embedder
    
    embedder = Embedder()
    print(f"Ollama base URL: {embedder.ollama_base_url}")
    print(f"Target dims: {embedder.dimensions}")
    
    texts = ["hello world", "machine learning is a subset of AI", "graph rag for knowledge"]
    
    print(f"\nEmbedding {len(texts)} texts...")
    embeddings = await embedder.embed_texts(texts)
    
    print(f"Got {len(embeddings)} embeddings")
    for i, (text, emb) in enumerate(zip(texts, embeddings)):
        print(f"  [{i}] dims={len(emb)}, text=\"{text[:40]}\"")
    
    assert all(len(e) == embedder.dimensions for e in embeddings), "Dimension mismatch!"
    print(f"\nAll embeddings match target dimension ({embedder.dimensions}). OK")

asyncio.run(test())
