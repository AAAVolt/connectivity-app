"""Tests for the cells API endpoint."""

from collections import namedtuple

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db import get_db


CellRow = namedtuple(
    "CellRow", ["id", "cell_code", "population", "combined_score", "combined_score_normalized"]
)
ScoreRow = namedtuple("ScoreRow", ["mode", "purpose", "score", "score_normalized"])


@pytest.fixture(autouse=True)
def _mock_db():
    """Override DB dependency with an async mock session."""
    mock_session = AsyncMock()

    async def override():
        yield mock_session

    app.dependency_overrides[get_db] = override
    yield mock_session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_cell_not_found(_mock_db: AsyncMock) -> None:
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    _mock_db.execute.return_value = result_mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/cells/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_cell_found(_mock_db: AsyncMock) -> None:
    cell_row = CellRow(
        id=1,
        cell_code="E430200_N4790300",
        population=150.0,
        combined_score=42.5,
        combined_score_normalized=67.8,
    )

    cell_result = MagicMock()
    cell_result.one_or_none.return_value = cell_row

    score_rows = [ScoreRow("WALK", "jobs", 1.5, 55.0)]
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
    assert data["scores"][0]["mode"] == "WALK"
    assert data["scores"][0]["purpose"] == "jobs"
