"""Area statistics endpoint."""

import json

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import AreaStatsRequest, AreaStatsResponse
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.post("/area", response_model=AreaStatsResponse)
async def get_area_stats(
    request: AreaStatsRequest,
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> AreaStatsResponse:
    """Population-weighted average connectivity for an arbitrary polygon.

    Accepts a GeoJSON geometry and returns statistics for grid cells
    whose centroid falls within the polygon.
    """
    geojson_str = json.dumps(request.geometry)

    result = await db.execute(
        text("""
            WITH area AS (
                SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326) AS geom
            ),
            cells_in_area AS (
                SELECT gc.id, gc.population, cs.combined_score_normalized
                FROM grid_cells gc
                LEFT JOIN combined_scores cs
                    ON cs.cell_id = gc.id AND cs.tenant_id = gc.tenant_id
                JOIN area a ON ST_Intersects(gc.centroid, a.geom)
                WHERE gc.tenant_id = :tid
            )
            SELECT
                COUNT(*)                      AS cell_count,
                COALESCE(SUM(population), 0)  AS population,
                AVG(combined_score_normalized) AS avg_score,
                CASE
                    WHEN SUM(population) > 0 THEN
                        SUM(population * COALESCE(combined_score_normalized, 0))
                        / SUM(population)
                    ELSE NULL
                END AS weighted_avg_score
            FROM cells_in_area
        """),
        {"geojson": geojson_str, "tid": tenant.tenant_id},
    )
    row = result.one()

    return AreaStatsResponse(
        cell_count=row.cell_count,
        population=float(row.population),
        avg_combined_score=(
            float(row.avg_score) if row.avg_score is not None else None
        ),
        weighted_avg_combined_score=(
            float(row.weighted_avg_score) if row.weighted_avg_score is not None else None
        ),
    )
