from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "instagpt-graphrag"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # LLM Provider Selection
    LLM_PROVIDER: str = "openai"  # openai, openrouter, nvidia, google, ollama, colab
    LLM_FALLBACK_ENABLED: bool = True
    LLM_FALLBACK_CHAIN: str = "openrouter,nvidia,google"  # comma-separated fallback order

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIM: int = 1536
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_CHAT_MODEL: str = "anthropic/claude-3-haiku"

    # NVIDIA API
    NVIDIA_API_KEY: str = ""
    NVIDIA_CHAT_MODEL: str = "nvidia/nemotron-3-ultra"

    # Google API (Gemini)
    GOOGLE_API_KEY: str = ""
    GOOGLE_CHAT_MODEL: str = "gemini-1.5-flash"

    # Ollama (Local LLM)
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_CHAT_MODEL: str = "qwen2.5:7b"
    OLLAMA_API_KEY: str = "ollama"  # Not needed, but required for OpenAI client

    # Colab (Remote LLM via Google Colab + vLLM)
    COLAB_BASE_URL: str = ""  # Set to ngrok URL from Colab notebook
    COLAB_CHAT_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    COLAB_API_KEY: str = "not-needed"  # vLLM default, no auth required

    # Qdrant Vector DB
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "knowledge_graph"

    # PostgreSQL Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/instagpt"

    # Neo4j Graph DB
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Web Search
    SEARCH_PROVIDER: str = "duckduckgo"
    SEARCH_MAX_RESULTS: int = 10
    SEARCH_TIMEOUT: int = 30

    # Pipeline
    MAX_CONCURRENT_URLS: int = 3
    MAX_CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    MIN_CHUNK_SIZE: int = 100
    EMBEDDING_BATCH_SIZE: int = 100

    # Categorization
    SIMILARITY_THRESHOLD: float = 0.75
    RERANK_TOP_K: int = 20
    FINAL_TOP_K: int = 5

    # Output
    OUTPUT_DIR: str = "./outputs"
    GRAPH_EXPORT_FORMAT: str = "graphml"

    # Playwright
    PLAYWRIGHT_BROWSER: str = "chromium"
    PLAYWRIGHT_HEADLESS: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()