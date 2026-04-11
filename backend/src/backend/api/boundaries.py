"""Boundary GeoJSON endpoints: region, municipalities, comarcas, nucleos."""

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from backend.api.schemas import parse_geometry
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import DuckDBSession, get_db

router = APIRouter(prefix="/boundaries", tags=["boundaries"])


@router.get("/region/geojson", response_class=Response)
def get_region_boundary(
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> Response:
    """Return the Bizkaia region boundary as GeoJSON."""
    result = db.execute(
        """
        SELECT id, name, boundary_type,
               ST_AsGeoJSON(geom) AS geometry
        FROM boundaries
        WHERE tenant_id = $tid
        """,
        {"tid": tenant.tenant_id},
    )

    features = [
        {
            "type": "Feature",
            "properties": {"id": row.id, "name": row.name, "type": row.boundary_type},
            "geometry": parse_geometry(row.geometry),
        }
        for row in result.fetchall()
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=3600, stale-while-revalidate=86400"},
    )


@router.get("/municipalities/geojson", response_class=Response)
def get_municipalities(
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> Response:
    """Return all municipality boundaries as GeoJSON."""
    result = db.execute(
        """
        SELECT id, muni_code, name,
               ST_AsGeoJSON(geom) AS geometry
        FROM municipalities
        WHERE tenant_id = $tid
        ORDER BY name
        """,
        {"tid": tenant.tenant_id},
    )

    features = [
        {
            "type": "Feature",
            "properties": {"id": row.id, "muni_code": row.muni_code, "name": row.name},
            "geometry": parse_geometry(row.geometry),
        }
        for row in result.fetchall()
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=3600, stale-while-revalidate=86400"},
    )


@router.get("/comarcas/geojson", response_class=Response)
def get_comarcas(
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> Response:
    """Return all comarca boundaries as GeoJSON."""
    result = db.execute(
        """
        SELECT id, comarca_code, name,
               ST_AsGeoJSON(geom) AS geometry
        FROM comarcas
        WHERE tenant_id = $tid
        ORDER BY name
        """,
        {"tid": tenant.tenant_id},
    )

    features = [
        {
            "type": "Feature",
            "properties": {"id": row.id, "comarca_code": row.comarca_code, "name": row.name},
            "geometry": parse_geometry(row.geometry),
        }
        for row in result.fetchall()
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=3600, stale-while-revalidate=86400"},
    )


@router.get("/nucleos/geojson", response_class=Response)
def get_nucleos(
    include_diseminado: bool = Query(
        False, description="Include dispersed (diseminado) areas (nucleo_num=99)"
    ),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> Response:
    """Return EUSTAT nucleo (settlement) boundaries as GeoJSON."""
    params: dict[str, object] = {"tid": tenant.tenant_id}
    diseminado_filter = "" if include_diseminado else "AND nucleo_num != '99'"

    result = db.execute(
        f"""
        SELECT id, code, nucleo_num, name, entity_name,
               muni_code, muni_name,
               ST_AsGeoJSON(geom) AS geometry
        FROM nucleos
        WHERE tenant_id = $tid {diseminado_filter}
        ORDER BY muni_name, name
        """,
        params,
    )

    features = [
        {
            "type": "Feature",
            "properties": {
                "id": row.id,
                "code": row.code,
                "nucleo_num": row.nucleo_num,
                "name": row.name,
                "entity_name": row.entity_name,
                "muni_code": row.muni_code,
                "muni_name": row.muni_name,
            },
            "geometry": parse_geometry(row.geometry),
        }
        for row in result.fetchall()
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=3600, stale-while-revalidate=86400"},
    )
