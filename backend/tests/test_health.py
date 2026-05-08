"""Tests for the liveness and readiness probes."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "bizkaia-backend"


@pytest.mark.asyncio
async def test_readiness_503_when_db_not_initialized() -> None:
    """While DuckDB is still loading (or after close_db()) we must return 503."""
    transport = ASGITransport(app=app)
    with patch("backend.api.health.is_ready", return_value=False):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/readiness")

    assert response.status_code == 503
    assert response.json()["status"] == "initializing"


@pytest.mark.asyncio
async def test_readiness_200_when_db_ready() -> None:
    transport = ASGITransport(app=app)
    with patch("backend.api.health.is_ready", return_value=True):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
