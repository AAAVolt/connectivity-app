"""Destinations GeoJSON endpoint."""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from backend.api.schemas import parse_geometry
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import DuckDBSession, get_db

router = APIRouter(prefix="/destinations", tags=["destinations"])


@router.get("/types")
def get_destination_types(
    db: DuckDBSession = Depends(get_db),
) -> list[dict[str, str]]:
    """Return all destination type codes and labels (for dynamic purpose filters)."""
    result = db.execute("SELECT code, label FROM destination_types ORDER BY code")
    return [{"code": row.code, "label": row.label} for row in result.fetchall()]


@router.get("/geojson", response_class=Response)
def get_destinations_geojson(
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> Response:
    """Return all destinations as a GeoJSON FeatureCollection."""
    result = db.execute(
        """
        SELECT
            d.id,
            d.name,
            dt.code AS type,
            dt.label AS type_label,
            d.weight,
            ST_AsGeoJSON(d.geom) AS geojson
        FROM destinations d
        JOIN destination_types dt ON d.type_id = dt.id
        WHERE d.tenant_id = $tid
        """,
        {"tid": tenant.tenant_id},
    )
    rows = result.fetchall()

    features = [
        {
            "type": "Feature",
            "properties": {
                "id": row.id,
                "name": row.name,
                "type": row.type,
                "type_label": row.type_label,
                "weight": row.weight,
            },
            "geometry": parse_geometry(row.geojson),
        }
        for row in rows
    ]

    geojson = {"type": "FeatureCollection", "features": features}
    return Response(
        content=json.dumps(geojson),
        media_type="application/geo+json",
    )
