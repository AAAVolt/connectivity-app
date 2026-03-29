"""Cell detail and GeoJSON endpoints."""

import json
import re
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import CellResponse, CellScoreDetail
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import get_db

router = APIRouter(prefix="/cells", tags=["cells"])

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
DEFAULT_DEPARTURE_TIME = "08:00"
ALLOWED_RESOLUTIONS = (100, 500, 1000)


class TransportMode(str, Enum):
    WALK = "WALK"
    TRANSIT = "TRANSIT"


class Purpose(str, Enum):
    jobs = "jobs"
    education = "education"
    health = "health"
    retail = "retail"


class Metric(str, Enum):
    score = "score"
    travel_time = "travel_time"


def _validate_departure_time(dep: str) -> str:
    """Validate and return a departure_time string like '08:00'."""
    if not _TIME_RE.match(dep):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid departure_time format: '{dep}'. Expected HH:MM.",
        )
    hh, mm = int(dep[:2]), int(dep[3:])
    if hh > 23 or mm not in (0, 30):
        raise HTTPException(
            status_code=400,
            detail=f"departure_time must be on a 30-minute boundary (00 or 30), got '{dep}'.",
        )
    return dep


# ---------------------------------------------------------------------------
# SQL helpers for multi-resolution grids
# ---------------------------------------------------------------------------


def _build_base_query(
    mode: TransportMode | None,
    purpose: Purpose | None,
    metric: Metric,
    params: dict[str, object],
) -> str:
    """Return SQL selecting ``(id, cell_code, population, score, geom)`` per 100 m cell.

    Mutates *params* to add bind variables for the chosen filters.
    The returned query uses raw ``gc.geom`` (not GeoJSON) so the caller
    can either convert directly or aggregate before converting.
    """
    if metric == Metric.travel_time and mode is not None and purpose is not None:
        params["mode"] = mode.value
        params["purpose"] = purpose.value
        return """
            SELECT gc.id, gc.cell_code, gc.population,
                   mt.min_travel_time_minutes AS score, gc.geom
            FROM grid_cells gc
            LEFT JOIN min_travel_times mt
                ON mt.cell_id = gc.id AND mt.tenant_id = gc.tenant_id
                AND mt.mode = :mode AND mt.purpose = :purpose
                AND mt.departure_time = :dep_time
            WHERE gc.tenant_id = :tid
        """

    if metric == Metric.travel_time and purpose is not None:
        params["purpose"] = purpose.value
        return """
            SELECT gc.id, gc.cell_code, gc.population,
                   MIN(mt.min_travel_time_minutes) AS score, gc.geom
            FROM grid_cells gc
            LEFT JOIN min_travel_times mt
                ON mt.cell_id = gc.id AND mt.tenant_id = gc.tenant_id
                AND mt.purpose = :purpose
                AND mt.departure_time = :dep_time
            WHERE gc.tenant_id = :tid
            GROUP BY gc.id, gc.cell_code, gc.population, gc.geom
        """

    if metric == Metric.travel_time and mode is not None:
        params["mode"] = mode.value
        return """
            SELECT gc.id, gc.cell_code, gc.population,
                   AVG(mt.min_travel_time_minutes) AS score, gc.geom
            FROM grid_cells gc
            LEFT JOIN min_travel_times mt
                ON mt.cell_id = gc.id AND mt.tenant_id = gc.tenant_id
                AND mt.mode = :mode
                AND mt.departure_time = :dep_time
            WHERE gc.tenant_id = :tid
            GROUP BY gc.id, gc.cell_code, gc.population, gc.geom
        """

    if metric == Metric.travel_time:
        return """
            SELECT gc.id, gc.cell_code, gc.population,
                   AVG(mt.min_travel_time_minutes) AS score, gc.geom
            FROM grid_cells gc
            LEFT JOIN min_travel_times mt
                ON mt.cell_id = gc.id AND mt.tenant_id = gc.tenant_id
                AND mt.departure_time = :dep_time
            WHERE gc.tenant_id = :tid
            GROUP BY gc.id, gc.cell_code, gc.population, gc.geom
        """

    if mode is not None and purpose is not None:
        params["mode"] = mode.value
        params["purpose"] = purpose.value
        return """
            SELECT gc.id, gc.cell_code, gc.population,
                   cs.score_normalized AS score, gc.geom
            FROM grid_cells gc
            LEFT JOIN connectivity_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                AND cs.mode = :mode AND cs.purpose = :purpose
                AND cs.departure_time = :dep_time
            WHERE gc.tenant_id = :tid
        """

    if mode is not None:
        params["mode"] = mode.value
        return """
            SELECT gc.id, gc.cell_code, gc.population,
                   AVG(cs.score_normalized) AS score, gc.geom
            FROM grid_cells gc
            LEFT JOIN connectivity_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                AND cs.mode = :mode
                AND cs.departure_time = :dep_time
            WHERE gc.tenant_id = :tid
            GROUP BY gc.id, gc.cell_code, gc.population, gc.geom
        """

    if purpose is not None:
        params["purpose"] = purpose.value
        return """
            SELECT gc.id, gc.cell_code, gc.population,
                   AVG(cs.score_normalized) AS score, gc.geom
            FROM grid_cells gc
            LEFT JOIN connectivity_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                AND cs.purpose = :purpose
                AND cs.departure_time = :dep_time
            WHERE gc.tenant_id = :tid
            GROUP BY gc.id, gc.cell_code, gc.population, gc.geom
        """

    return """
        SELECT gc.id, gc.cell_code, gc.population,
               cs.combined_score_normalized AS score, gc.geom
        FROM grid_cells gc
        LEFT JOIN combined_scores cs
            ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
            AND cs.departure_time = :dep_time
        WHERE gc.tenant_id = :tid
    """


# Aggregation wrapper – groups 100 m cells into a coarser resolution.
# Uses population-weighted averaging for scores; falls back to simple
# AVG when all population in a group is zero.
# The {base_sql} placeholder is replaced at call-time.
_AGGREGATE_SQL = """
    WITH base AS ({base_sql})
    SELECT
        'E' || (floor(substring(cell_code FROM 'E(\\d+)_N')::int / :res) * :res)::int
        || '_N' || (floor(substring(cell_code FROM '_N(\\d+)')::int / :res) * :res)::int
        AS cell_code,
        SUM(population) AS population,
        COALESCE(
            SUM(population * score)
            / NULLIF(SUM(CASE WHEN score IS NOT NULL THEN population END), 0),
            AVG(score)
        ) AS score,
        ST_AsGeoJSON(ST_Envelope(ST_Collect(geom)))::json AS geometry
    FROM base
    GROUP BY
        floor(substring(cell_code FROM 'E(\\d+)_N')::int / :res),
        floor(substring(cell_code FROM '_N(\\d+)')::int / :res)
"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/departure-times")
async def get_available_departure_times(
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return sorted list of departure_time slots that have computed scores."""
    result = await db.execute(
        text("""
            SELECT DISTINCT departure_time
            FROM connectivity_scores
            WHERE tenant_id = :tid
            ORDER BY departure_time
        """),
        {"tid": tenant.tenant_id},
    )
    return [row[0] for row in result.fetchall()]


@router.get("/geojson", response_class=Response)
async def get_cells_geojson(
    mode: TransportMode | None = Query(None, description="Filter by transport mode"),
    purpose: Purpose | None = Query(None, description="Filter by destination purpose"),
    metric: Metric = Query(Metric.score, description="Metric to return: score or travel_time"),
    resolution: int = Query(100, description="Grid resolution in meters: 100, 500, or 1000"),
    departure_time: str = Query(
        DEFAULT_DEPARTURE_TIME,
        description="Departure time of day (HH:MM, 30-min intervals)",
    ),
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return grid cells as GeoJSON with scores or min travel times.

    *resolution* controls the grid cell size returned:

    - **100** (default): base 100 m cells.
    - **500**: 500 m cells (5x5 base cells, population-weighted scores).
    - **1000**: 1 km cells (10x10 base cells, population-weighted scores).

    departure_time selects which time-of-day slot to display (e.g. "08:00").
    metric=score (default): accessibility score (0-100).
    metric=travel_time: minutes to nearest destination of that purpose.
    """
    if resolution not in ALLOWED_RESOLUTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"resolution must be one of {ALLOWED_RESOLUTIONS}",
        )

    dep_time = _validate_departure_time(departure_time)
    params: dict[str, object] = {"tid": tenant.tenant_id, "dep_time": dep_time}
    base_sql = _build_base_query(mode, purpose, metric, params)

    if resolution == 100:
        sql = f"""
            SELECT id, cell_code, population, score,
                   ST_AsGeoJSON(geom)::json AS geometry
            FROM ({base_sql}) AS base
        """
    else:
        params["res"] = resolution
        sql = _AGGREGATE_SQL.format(base_sql=base_sql)

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    features = []
    for row in rows:
        props: dict[str, object] = {
            "cell_code": row.cell_code,
            "population": row.population,
            "score": float(row.score) if row.score is not None else None,
        }
        if resolution == 100:
            props["id"] = row.id
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": row.geometry,
        })

    geojson = {"type": "FeatureCollection", "features": features}
    return Response(
        content=json.dumps(geojson),
        media_type="application/geo+json",
    )


@router.get("/{cell_id}", response_model=CellResponse)
async def get_cell(
    cell_id: int,
    departure_time: str = Query(
        DEFAULT_DEPARTURE_TIME,
        description="Departure time of day (HH:MM)",
    ),
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> CellResponse:
    """Return cell info, connectivity scores, and combined score."""
    dep_time = _validate_departure_time(departure_time)

    result = await db.execute(
        text("""
            SELECT gc.id, gc.cell_code, gc.population,
                   cs.combined_score, cs.combined_score_normalized
            FROM grid_cells gc
            LEFT JOIN combined_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                AND cs.departure_time = :dep_time
            WHERE gc.id = :cell_id AND gc.tenant_id = :tid
        """),
        {"cell_id": cell_id, "tid": tenant.tenant_id, "dep_time": dep_time},
    )
    row = result.one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Cell not found")

    scores_result = await db.execute(
        text("""
            SELECT mode, purpose, score, score_normalized
            FROM connectivity_scores
            WHERE cell_id = :cell_id AND tenant_id = :tid
                AND departure_time = :dep_time
            ORDER BY mode, purpose
        """),
        {"cell_id": cell_id, "tid": tenant.tenant_id, "dep_time": dep_time},
    )

    scores = [
        CellScoreDetail(
            mode=s.mode,
            purpose=s.purpose,
            score=s.score,
            score_normalized=s.score_normalized,
        )
        for s in scores_result.fetchall()
    ]

    return CellResponse(
        id=row.id,
        cell_code=row.cell_code,
        population=row.population,
        combined_score=row.combined_score,
        combined_score_normalized=row.combined_score_normalized,
        scores=scores,
    )
