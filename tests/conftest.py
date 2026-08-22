"""Shared test fixtures for instagpt-graphrag.

Provides:
- MemoryRecorder: in-memory recorder for unit tests (no DB)
- FakeVectorStore / FakeEmbedder: deterministic fakes
- NetworkXGraphStore: lightweight graph store for unit tests
- pg_engine / pg_session: async Postgres fixtures for integration tests
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure local tests package takes precedence over any global 'tests' package
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import asyncio
import hashlib
from typing import Any

import pytest
import pytest_asyncio

# ─── In-Memory Recorder (no DB needed) ───────────────────────────────────────
from src.pipeline.recorder import BaseRecorder


class MemoryRecorder(BaseRecorder):
    """In-memory recorder for unit tests. Tracks steps without any DB."""

    def __init__(self):
        self.steps: dict[str, str] = {}  # step_name → status
        self.checkpoints: dict[str, dict[str, Any]] = {}
        self.errors: dict[str, str] = {}
        self.heartbeat_count = 0

    async def begin_step(self, step_name: str) -> None:
        self.steps[step_name] = "running"

    async def complete_step(self, step_name: str, checkpoint_data: dict[str, Any]) -> None:
        self.steps[step_name] = "completed"
        self.checkpoints[step_name] = checkpoint_data

    async def fail_step(self, step_name: str, error: str) -> None:
        self.steps[step_name] = "failed"
        self.errors[step_name] = error

    async def is_step_completed(self, step_name: str) -> bool:
        return self.steps.get(step_name) == "completed"

    async def get_checkpoint(self, step_name: str) -> dict[str, Any]:
        return self.checkpoints.get(step_name, {})

    async def heartbeat(self) -> None:
        self.heartbeat_count += 1


# ─── Fake Vector Store ────────────────────────────────────────────────────────

class FakeVectorStore:
    """In-memory vector store for unit tests."""

    def __init__(self):
        self.chunks: list[Any] = []
        self.source_url: str | None = None

    def upsert_chunks(self, chunks: list[Any], source_url: str) -> None:
        self.chunks = list(chunks)
        self.source_url = source_url


# ─── Fake Embedder ────────────────────────────────────────────────────────────

class FakeEmbedder:
    """Deterministic embedder for unit tests — returns fixed-dimension vectors."""

    def __init__(self, dim: int = 8):
        self.dim = dim
        self.openai_client = None

    async def embed_chunks(self, chunks: list[Any]) -> list[Any]:
        for i, chunk in enumerate(chunks):
            # Deterministic: hash chunk text to seed a simple vector
            seed = int(hashlib.md5(chunk.text.encode()).hexdigest()[:8], 16)
            chunk.embedding = [((seed >> (j * 4)) & 0xF) / 15.0 for j in range(self.dim)]
        return chunks

    async def embed_text(self, text: str) -> list[float]:
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        return [((seed >> (j * 4)) & 0xF) / 15.0 for j in range(self.dim)]


# ─── Fake LLM Client ─────────────────────────────────────────────────────────

class FakeLLMClient:
    """Returns canned responses for entity extraction / categorization."""

    def __init__(self):
        self.call_count = 0

    async def chat_completion(self, messages, temperature=0.7, max_tokens=1000):
        self.call_count += 1
        return {
            "content": '{"entities": [], "relationships": []}',
            "usage": {"total_tokens": 100},
        }


# ─── Integration Test Fixtures (require live Postgres) ────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Override default event loop to be session-scoped."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    """Create an async engine connected to the test database.

    Expects DATABASE_URL env var or falls back to the default dev URL.
    The database is created/dropped per session.
    """
    import os

    from sqlalchemy.ext.asyncio import create_async_engine

    from src.database.base import Base

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/instagpt_test",
    )

    engine = create_async_engine(database_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine):
    """Yield a fresh async session for each test, rolled back after the test."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def pg_crud(pg_session):
    """Yield a CRUDOperations bound to the test session."""
    from src.database.crud import CRUDOperations
    return CRUDOperations(pg_session)
