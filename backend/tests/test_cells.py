"""Tests for the cells API endpoint."""

from collections import namedtuple

import pytest
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db import get_db
from backend.api.cache import clear_all as clear_result_cache


CellRow = namedtuple(
    "CellRow", ["id", "cell_code", "population", "combined_score", "combined_score_normalized"]
)
ScoreRow = namedtuple("ScoreRow", ["mode", "purpose", "score", "score_normalized"])


@pytest.fixture(autouse=True)
def _mock_db():
    """Override DB dependency with a sync mock session (DuckDBSession is sync)."""
    clear_result_cache()
    mock_session = MagicMock()

    def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    yield mock_session
    app.dependency_overrides.clear()
    clear_result_cache()


@pytest.mark.asyncio
async def test_get_cell_not_found(_mock_db: MagicMock) -> None:
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    _mock_db.execute.return_value = result_mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/cells/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_geojson_invalid_resolution(_mock_db: MagicMock) -> None:
    """resolution must be one of 250, 500, or 1000."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/cells/geojson?resolution=100")

    assert response.status_code == 400
    assert "resolution" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_geojson_resolution_250_accepted(_mock_db: MagicMock) -> None:
    """resolution=250 (base) should be accepted and execute without error."""
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []
    _mock_db.execute.return_value = result_mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/cells/geojson?resolution=250")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["features"] == []


@pytest.mark.asyncio
async def test_geojson_resolution_500_accepted(_mock_db: MagicMock) -> None:
    """resolution=500 should be accepted and execute without error."""
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []
    _mock_db.execute.return_value = result_mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/cells/geojson?resolution=500")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["features"] == []


@pytest.mark.asyncio
async def test_geojson_resolution_1000_accepted(_mock_db: MagicMock) -> None:
    """resolution=1000 should also be accepted."""
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []
    _mock_db.execute.return_value = result_mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/cells/geojson?resolution=1000")

    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"


@pytest.mark.asyncio
async def test_get_cell_found(_mock_db: MagicMock) -> None:
    cell_row = CellRow(
        id=1,
        cell_code="E430200_N4790300",
        population=150.0,
        combined_score=42.5,
        combined_score_normalized=67.8,
    )

    cell_result = MagicMock()
    cell_result.one_or_none.return_value = cell_row

    score_rows = [ScoreRow("TRANSIT", "hospital", 1.5, 55.0)]
    scores_result = MagicMock()
    scores_result.fetchall.return_value = score_rows

    _mock_db.execute.side_effect = [cell_result, scores_result]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/cells/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["cell_code"] == "E430200_N4790300"
    assert data["population"] == 150.0
    assert data["combined_score_normalized"] == 67.8
    assert len(data["scores"]) == 1
    assert data["scores"][0]["mode"] == "TRANSIT"
    assert data["scores"][0]["purpose"] == "hospital"
