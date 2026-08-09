"""API route modules."""
from src.api.routes.video import router as video_router
from src.api.routes.graph import router as graph_router
from src.api.routes.search import router as search_router
from src.api.routes.notebook import router as notebook_router

__all__ = [
    "video_router",
    "graph_router",
    "search_router",
    "notebook_router",
]
