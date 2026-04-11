"""Tests for the dashboard analytics API endpoints."""

from collections import namedtuple

import pytest
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db import get_db
from backend.api.cache import clear_all as clear_result_cache


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


# -- /dashboard/summary -------------------------------------------------------

SummaryRow = namedtuple(
    "SummaryRow",
    [
        "total_cells",
        "populated_cells",
        "total_population",
        "cells_with_scores",
        "avg_score",
        "weighted_avg_score",
        "median_score",
    ],
)

CountsRow = namedtuple(
    "CountsRow", ["dest_count", "stop_count", "route_count", "muni_count", "comarca_count"]
)


@pytest.mark.asyncio
async def test_summary(_mock_db: MagicMock) -> None:
    main_result = MagicMock()
    main_result.one.return_value = SummaryRow(
        total_cells=5000,
        populated_cells=3200,
        total_population=120000.0,
        cells_with_scores=4800,
        avg_score=55.3,
        weighted_avg_score=61.2,
        median_score=58.0,
    )

    # _safe_count calls db.execute() once per table (5 total)
    def make_count_result(count: int) -> MagicMock:
        r = MagicMock()
        r.one.return_value = namedtuple("C", ["c"])(c=count)
        return r

    _mock_db.execute.side_effect = [
        main_result,
        make_count_result(250),   # destinations
        make_count_result(1200),  # gtfs_stops
        make_count_result(45),    # gtfs_routes
        make_count_result(112),   # municipalities
        make_count_result(7),     # comarcas
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/dashboard/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cells"] == 5000
    assert data["populated_cells"] == 3200
    assert data["total_population"] == 120000.0
    assert data["weighted_avg_score"] == 61.2
    assert data["destination_count"] == 250
    assert data["transit_stop_count"] == 1200
    assert data["municipality_count"] == 112
    assert data["comarca_count"] == 7


# -- /dashboard/score-distribution --------------------------------------------

BucketRow = namedtuple("BucketRow", ["bucket", "cell_count", "population"])


@pytest.mark.asyncio
async def test_score_distribution(_mock_db: MagicMock) -> None:
    result = MagicMock()
    result.fetchall.return_value = [
        BucketRow(bucket=1, cell_count=100, population=500.0),
        BucketRow(bucket=5, cell_count=800, population=15000.0),
        BucketRow(bucket=10, cell_count=200, population=3000.0),
    ]
    _mock_db.execute.return_value = result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/dashboard/score-distribution")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    assert data[0]["range_label"] == "0-10"
    assert data[0]["cell_count"] == 100
    assert data[4]["range_label"] == "40-50"
    assert data[4]["cell_count"] == 800
    assert data[9]["range_label"] == "90-100"
    assert data[9]["cell_count"] == 200
    # Unfilled buckets should be zero
    assert data[1]["cell_count"] == 0
    assert data[1]["population"] == 0.0


# -- /dashboard/purpose-breakdown ----------------------------------------------

DestTypeRow = namedtuple("DestTypeRow", ["code", "label"])
PurposeRow = namedtuple(
    "PurposeRow",
    ["mode", "purpose", "avg_score", "weighted_avg_score", "cell_count"],
)
TravelTimeRow = namedtuple("TravelTimeRow", ["mode", "purpose", "avg_tt"])


@pytest.mark.asyncio
async def test_purpose_breakdown(_mock_db: MagicMock) -> None:
    dt_result = MagicMock()
    dt_result.fetchall.return_value = [
        DestTypeRow("hospital", "Hospital"),
    ]

    scores_result = MagicMock()
    scores_result.fetchall.return_value = [
        PurposeRow("TRANSIT", "hospital", 72.5, 75.0, 4500),
    ]

    tt_result = MagicMock()
    tt_result.fetchall.return_value = [
        TravelTimeRow("TRANSIT", "hospital", 22.5),
    ]

    _mock_db.execute.side_effect = [dt_result, scores_result, tt_result]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/dashboard/purpose-breakdown")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    transit = data[0]
    assert transit["purpose"] == "hospital"
    assert transit["purpose_label"] == "Hospital"
    assert transit["weighted_avg_score"] == 75.0
    assert transit["avg_travel_time"] == 22.5


# -- /dashboard/municipality-ranking ------------------------------------------

MuniRow = namedtuple(
    "MuniRow",
    ["name", "code", "cell_count", "population", "avg_score", "weighted_avg_score"],
)


@pytest.mark.asyncio
async def test_municipality_ranking(_mock_db: MagicMock) -> None:
    result = MagicMock()
    result.fetchall.return_value = [
        MuniRow("Bilbao", "48020", 1200, 350000.0, 78.5, 80.1),
        MuniRow("Getxo", "48044", 400, 80000.0, 65.0, 63.2),
    ]
    _mock_db.execute.return_value = result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/dashboard/municipality-ranking")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "Bilbao"
    assert data[0]["weighted_avg_score"] == 80.1
    assert data[1]["name"] == "Getxo"


# -- /dashboard/comarca-ranking -----------------------------------------------

ComarcaRow = namedtuple(
    "ComarcaRow",
    ["name", "code", "cell_count", "population", "avg_score", "weighted_avg_score"],
)


@pytest.mark.asyncio
async def test_comarca_ranking(_mock_db: MagicMock) -> None:
    result = MagicMock()
    result.fetchall.return_value = [
        ComarcaRow("GRAN BILBAO", "05", 5000, 800000.0, 70.0, 72.5),
        ComarcaRow("DURANGUESADO", "03", 2000, 100000.0, 45.0, 42.0),
    ]
    _mock_db.execute.return_value = result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/dashboard/comarca-ranking")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "GRAN BILBAO"
    assert data[0]["weighted_avg_score"] == 72.5
    assert data[1]["name"] == "DURANGUESADO"


# -- /dashboard/service-coverage -----------------------------------------------

CoverageRow = namedtuple(
    "CoverageRow",
    [
        "purpose",
        "mode",
        "total_cells",
        "total_population",
        "pop_15min",
        "pop_30min",
        "pop_45min",
        "pop_60min",
        "avg_tt",
        "median_tt",
    ],
)


@pytest.mark.asyncio
async def test_service_coverage(_mock_db: MagicMock) -> None:
    dt_result = MagicMock()
    dt_result.fetchall.return_value = [
        DestTypeRow("hospital", "Hospital"),
    ]

    data_result = MagicMock()
    data_result.fetchall.return_value = [
        CoverageRow(
            purpose="hospital",
            mode="TRANSIT",
            total_cells=4000,
            total_population=100000.0,
            pop_15min=30000.0,
            pop_30min=70000.0,
            pop_45min=90000.0,
            pop_60min=98000.0,
            avg_tt=28.5,
            median_tt=25.0,
        ),
    ]

    _mock_db.execute.side_effect = [dt_result, data_result]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/dashboard/service-coverage")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    h = data[0]
    assert h["purpose"] == "hospital"
    assert h["purpose_label"] == "Hospital"
    assert h["pct_pop_15min"] == 30.0
    assert h["pct_pop_30min"] == 70.0
    assert h["pct_pop_60min"] == 98.0
    assert h["avg_travel_time"] == 28.5
    assert h["median_travel_time"] == 25.0


# -- validation ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_bad_departure_time(_mock_db: MagicMock) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/dashboard/summary?departure_time=09:15")

    assert resp.status_code == 400
