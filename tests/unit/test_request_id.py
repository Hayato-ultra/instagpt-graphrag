"""Tests for request ID middleware (TODO #51 observability)."""
import uuid
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Bind request_id to loguru context for correlated logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        with logger.contextualize(request_id=request_id):
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
        return response


def _make_client():
    """Create a minimal app with the middleware for testing."""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    return TestClient(app)


class TestRequestIDMiddleware:
    """Verify request ID is generated and returned in response headers."""

    def test_generates_request_id(self):
        """Response includes X-Request-ID header when none provided."""
        client = _make_client()
        resp = client.get("/ok")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) == 8

    def test_preserves_provided_request_id(self):
        """Response echoes back client-provided X-Request-ID."""
        client = _make_client()
        resp = client.get("/ok", headers={"X-Request-ID": "my-trace-123"})
        assert resp.headers["X-Request-ID"] == "my-trace-123"

    def test_unique_per_request(self):
        """Each request gets a different auto-generated ID."""
        client = _make_client()
        ids = {client.get("/ok").headers["x-request-id"] for _ in range(5)}
        assert len(ids) == 5
