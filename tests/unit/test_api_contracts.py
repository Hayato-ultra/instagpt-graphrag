"""API contract tests for /api/jobs, /api/search, /api/graph endpoints.

Validates response schemas, status codes, and error handling.
Uses app.dependency_overrides to avoid real DB calls.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api import RequestIDMiddleware, RateLimitMiddleware


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    from src.api import app
    return TestClient(app)


class TestJobsAPI:
    """Contract tests for /api/jobs endpoints."""

    def test_list_jobs_returns_array(self, client):
        """GET /api/jobs returns a list (may be empty)."""
        from src.api import app
        from src.api.routes import get_db

        mock_crud = AsyncMock()
        mock_crud.list_pipeline_jobs = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_crud
        try:
            resp = client.get("/api/jobs")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_jobs_accepts_status_filter(self, client):
        """GET /api/jobs?status=completed is a valid query."""
        from src.api import app
        from src.api.routes import get_db

        mock_crud = AsyncMock()
        mock_crud.list_pipeline_jobs = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_crud
        try:
            resp = client.get("/api/jobs", params={"status": "completed"})
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_list_jobs_rejects_invalid_limit(self, client):
        """GET /api/jobs?limit=-1 returns 422."""
        resp = client.get("/api/jobs", params={"limit": -1})
        assert resp.status_code == 422

    def test_list_jobs_limit_and_offset(self, client):
        """GET /api/jobs?limit=10&offset=5 are accepted."""
        from src.api import app
        from src.api.routes import get_db

        mock_crud = AsyncMock()
        mock_crud.list_pipeline_jobs = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_crud
        try:
            resp = client.get("/api/jobs", params={"limit": 10, "offset": 5})
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_list_jobs_rejects_negative_limit(self, client):
        """GET /api/jobs?limit=-1 returns 422."""
        resp = client.get("/api/jobs", params={"limit": -1})
        assert resp.status_code == 422

    def test_get_job_not_found(self, client):
        """GET /api/jobs/{id} returns 404 for missing job."""
        from src.api import app
        from src.api.routes import get_db

        mock_crud = AsyncMock()
        mock_crud.get_pipeline_job_by_id = AsyncMock(return_value=None)
        app.dependency_overrides[get_db] = lambda: mock_crud
        try:
            resp = client.get("/api/jobs/nonexistent-id")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Job not found"


class TestSearchAPI:
    """Contract tests for /api/search endpoint."""

    def test_search_requires_body(self, client):
        """POST /api/search without body returns 422."""
        resp = client.post("/api/search")
        assert resp.status_code == 422

    def test_search_accepts_query(self, client):
        """POST /api/search with query dict is accepted."""
        mock_searcher = AsyncMock()
        mock_searcher.search = AsyncMock(return_value=[])
        with patch("src.api.searcher", mock_searcher):
            resp = client.post("/api/search", json={"query": "docker"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)


class TestGraphAPI:
    """Contract tests for /api/graph endpoints."""

    def test_graph_stats(self, client):
        """GET /api/graph/stats returns entity/relationship counts."""
        mock_store = MagicMock()
        stats = {"total_entities": 0, "total_relationships": 0}
        mock_store.get_stats = AsyncMock(return_value=stats)
        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            resp = client.get("/api/graph/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_entities" in data
        assert "total_relationships" in data

    def test_graph_entity_not_found(self, client):
        """GET /api/graph/entity/{name} returns 404 when entity doesn't exist."""
        mock_store = MagicMock()
        mock_store.get_entity = AsyncMock(return_value=None)
        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            resp = client.get("/api/graph/entity/nonexistent")
        assert resp.status_code == 404

    def test_graph_node_not_found(self, client):
        """GET /api/graph/node/{type}/{id} returns 404 when node doesn't exist."""
        mock_store = MagicMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_store.driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_store.driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            resp = client.get("/api/graph/node/concept/nonexistent")
        assert resp.status_code == 404

    def test_graph_video_empty(self, client):
        """GET /api/graph/video/{id} returns empty nodes when no records found."""
        mock_store = MagicMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_store.driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_store.driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("src.api.routes.graph.get_graph_store", return_value=mock_store):
            resp = client.get("/api/graph/video/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []


class TestVideoAPI:
    """Contract tests for /api/video endpoints."""

    def test_analyze_requires_body(self, client):
        """POST /api/video/analyze without body returns 422."""
        resp = client.post("/api/video/analyze")
        assert resp.status_code == 422


class TestHealthAPI:
    """Contract tests for /health endpoint."""

    def test_health_returns_ok(self, client):
        """GET /health returns status ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestRateLimit:
    """Contract tests for rate limiting."""

    def test_rate_limit_allows_normal_requests(self, client):
        """Normal request count is allowed."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_rate_limit_middleware_exists(self):
        """Rate limit middleware is configured on the app."""
        from src.api import app
        middleware_names = [m.cls.__name__ for m in app.user_middleware]
        assert "RateLimitMiddleware" in middleware_names
