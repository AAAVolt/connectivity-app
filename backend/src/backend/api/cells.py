"""Cell detail and GeoJSON endpoints."""

import json
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


class TransportMode(str, Enum):
    WALK = "WALK"
    TRANSIT = "TRANSIT"


class Purpose(str, Enum):
    jobs = "jobs"
    education = "education"
    health = "health"
    retail = "retail"


@router.get("/geojson", response_class=Response)
async def get_cells_geojson(
    mode: TransportMode | None = Query(None, description="Filter by transport mode"),
    purpose: Purpose | None = Query(None, description="Filter by destination purpose"),
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return grid cells as GeoJSON with scores.

    Without filters: returns combined score (weighted average of all).
    With mode and/or purpose: returns filtered connectivity score.
    """
    params: dict[str, object] = {"tid": tenant.tenant_id}

    if mode is not None and purpose is not None:
        # Exact (mode, purpose) score
        sql = """
            SELECT gc.id, gc.cell_code, gc.population,
                   cs.score_normalized AS score,
                   ST_AsGeoJSON(gc.geom)::json AS geometry
            FROM grid_cells gc
            LEFT JOIN connectivity_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                AND cs.mode = :mode AND cs.purpose = :purpose
            WHERE gc.tenant_id = :tid
        """
        params["mode"] = mode.value
        params["purpose"] = purpose.value

    elif mode is not None:
        # Average across all purposes for this mode
        sql = """
            SELECT gc.id, gc.cell_code, gc.population,
                   AVG(cs.score_normalized) AS score,
                   ST_AsGeoJSON(gc.geom)::json AS geometry
            FROM grid_cells gc
            LEFT JOIN connectivity_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                AND cs.mode = :mode
            WHERE gc.tenant_id = :tid
            GROUP BY gc.id, gc.cell_code, gc.population, gc.geom
        """
        params["mode"] = mode.value

    elif purpose is not None:
        # Average across all modes for this purpose
        sql = """
            SELECT gc.id, gc.cell_code, gc.population,
                   AVG(cs.score_normalized) AS score,
                   ST_AsGeoJSON(gc.geom)::json AS geometry
            FROM grid_cells gc
            LEFT JOIN connectivity_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                AND cs.purpose = :purpose
            WHERE gc.tenant_id = :tid
            GROUP BY gc.id, gc.cell_code, gc.population, gc.geom
        """
        params["purpose"] = purpose.value

    else:
        # No filter: combined score
        sql = """
            SELECT gc.id, gc.cell_code, gc.population,
                   cs.combined_score_normalized AS score,
                   ST_AsGeoJSON(gc.geom)::json AS geometry
            FROM grid_cells gc
            LEFT JOIN combined_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
            WHERE gc.tenant_id = :tid
        """

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    features = [
        {
            "type": "Feature",
            "properties": {
                "id": row.id,
                "cell_code": row.cell_code,
                "population": row.population,
                "score": float(row.score) if row.score is not None else None,
            },
            "geometry": row.geometry,
        }
        for row in rows
    ]

    geojson = {"type": "FeatureCollection", "features": features}
    return Response(
        content=json.dumps(geojson),
        media_type="application/geo+json",
    )


@router.get("/{cell_id}", response_model=CellResponse)
async def get_cell(
    cell_id: int,
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> CellResponse:
    """Return cell info, connectivity scores, and combined score."""
    result = await db.execute(
        text("""
            SELECT gc.id, gc.cell_code, gc.population,
                   cs.combined_score, cs.combined_score_normalized
            FROM grid_cells gc
            LEFT JOIN combined_scores cs
                ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
            WHERE gc.id = :cell_id AND gc.tenant_id = :tid
        """),
        {"cell_id": cell_id, "tid": tenant.tenant_id},
    )
    row = result.one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Cell not found")

    scores_result = await db.execute(
        text("""
            SELECT mode, purpose, score, score_normalized
            FROM connectivity_scores
            WHERE cell_id = :cell_id AND tenant_id = :tid
            ORDER BY mode, purpose
        """),
        {"cell_id": cell_id, "tid": tenant.tenant_id},
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
