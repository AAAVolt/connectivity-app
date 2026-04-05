"""Transit data endpoints – routes and stops from imported GTFS feeds."""

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from backend.api.schemas import parse_geometry
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import DuckDBSession, get_db

router = APIRouter(prefix="/transit", tags=["transit"])

# Route type -> color fallback (GTFS standard route_type codes)
ROUTE_TYPE_COLORS: dict[int, str] = {
    0: "#e11d48",  # Tram
    1: "#dc2626",  # Metro
    2: "#7c3aed",  # Rail
    3: "#2563eb",  # Bus
    4: "#0891b2",  # Ferry
    5: "#6b7280",  # Cable car
    6: "#6b7280",  # Gondola
    7: "#a855f7",  # Funicular
}


@router.get("/stops", response_class=Response)
def get_transit_stops(
    operator: str | None = Query(None, description="Filter by operator name"),
    db: DuckDBSession = Depends(get_db),
) -> Response:
    """Return transit stops as GeoJSON from imported GTFS data."""
    params: dict[str, object] = {}
    where = ""
    if operator:
        where = "AND operator = $operator"
        params["operator"] = operator

    result = db.execute(
        f"""
        SELECT id, operator, stop_id, stop_name,
               ST_AsGeoJSON(geom) AS geometry
        FROM gtfs_stops
        WHERE 1=1 {where}
        """,
        params,
    )
    rows = result.fetchall()

    features = [
        {
            "type": "Feature",
            "properties": {
                "id": row.id,
                "operator": row.operator,
                "stop_id": row.stop_id,
                "stop_name": row.stop_name,
            },
            "geometry": parse_geometry(row.geometry),
        }
        for row in rows
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
    )


@router.get("/routes", response_class=Response)
def get_transit_routes(
    operator: str | None = Query(None, description="Filter by operator name"),
    db: DuckDBSession = Depends(get_db),
) -> Response:
    """Return transit routes as GeoJSON from imported GTFS data."""
    params: dict[str, object] = {}
    where = ""
    if operator:
        where = "AND operator = $operator"
        params["operator"] = operator

    result = db.execute(
        f"""
        SELECT id, operator, route_id, route_name, route_type, route_color,
               ST_AsGeoJSON(geom) AS geometry
        FROM gtfs_routes
        WHERE geom IS NOT NULL {where}
        """,
        params,
    )
    rows = result.fetchall()

    features = []
    for row in rows:
        color = f"#{row.route_color}" if row.route_color else ROUTE_TYPE_COLORS.get(row.route_type, "#2563eb")
        features.append({
            "type": "Feature",
            "properties": {
                "id": row.id,
                "operator": row.operator,
                "route_id": row.route_id,
                "route_name": row.route_name,
                "route_type": row.route_type,
                "color": color,
            },
            "geometry": parse_geometry(row.geometry),
        })

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
    )


@router.get("/operators")
def get_operators(
    db: DuckDBSession = Depends(get_db),
) -> list[dict[str, object]]:
    """List all imported transit operators with route/stop counts."""
    result = db.execute("""
        SELECT
            r.operator,
            COUNT(DISTINCT r.id) AS route_count,
            COALESCE(s.stop_count, 0) AS stop_count
        FROM gtfs_routes r
        LEFT JOIN (
            SELECT operator, COUNT(*) AS stop_count FROM gtfs_stops GROUP BY operator
        ) s ON s.operator = r.operator
        GROUP BY r.operator, s.stop_count
        ORDER BY r.operator
    """)
    return [
        {"operator": row.operator, "routes": row.route_count, "stops": row.stop_count}
        for row in result.fetchall()
    ]
