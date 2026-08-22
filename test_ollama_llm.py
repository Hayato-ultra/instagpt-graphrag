import asyncio
from src.enrichment.llm_client import LLMClient


async def test():
    client = LLMClient()
    print(f"Primary provider: {client.primary_provider}")
    healthy = await client.check_ollama_health()
    print(f"Ollama healthy: {healthy}")

    try:
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "Say hi in 3 words"}],
            model="qwen2.5:7b",
        )
        print(f"Content: {result['content']}")
        print(f"Provider: {result['provider']}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test())
