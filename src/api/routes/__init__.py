"""Route modules for InstaGPT GraphRAG API."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session, CRUDOperations


async def get_db(session: AsyncSession = Depends(get_async_session)):
    """Dependency that yields CRUDOperations from an async session.

    The underlying get_async_session handles commit/rollback/close.
    Routes should NOT call session.commit() directly.
    """
    yield CRUDOperations(session)


video_router = APIRouter()
graph_router = APIRouter()
search_router = APIRouter()
notebook_router = APIRouter()
jobs_router = APIRouter()

from src.api.routes.video import router as video
from src.api.routes.graph import router as graph
from src.api.routes.search import router as search
from src.api.routes.notebook import router as notebook
from src.api.routes.jobs import router as jobs

video_router.include_router(video)
graph_router.include_router(graph)
search_router.include_router(search)
notebook_router.include_router(notebook)
jobs_router.include_router(jobs)
