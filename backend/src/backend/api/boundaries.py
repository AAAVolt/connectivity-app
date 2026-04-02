"""Boundary GeoJSON endpoints: region, municipalities, comarcas, nucleos."""

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import get_db

router = APIRouter(prefix="/boundaries", tags=["boundaries"])


@router.get("/region/geojson", response_class=Response)
async def get_region_boundary(
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the Bizkaia region boundary as GeoJSON."""
    result = await db.execute(
        text("""
            SELECT id, name, boundary_type,
                   ST_AsGeoJSON(geom)::json AS geometry
            FROM boundaries
            WHERE tenant_id = :tid
        """),
        {"tid": tenant.tenant_id},
    )
    rows = result.fetchall()

    features = [
        {
            "type": "Feature",
            "properties": {"id": row.id, "name": row.name, "type": row.boundary_type},
            "geometry": row.geometry,
        }
        for row in rows
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
    )


@router.get("/municipalities/geojson", response_class=Response)
async def get_municipalities(
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return all municipality boundaries as GeoJSON."""
    result = await db.execute(
        text("""
            SELECT id, muni_code, name,
                   ST_AsGeoJSON(geom)::json AS geometry
            FROM municipalities
            WHERE tenant_id = :tid
            ORDER BY name
        """),
        {"tid": tenant.tenant_id},
    )
    rows = result.fetchall()

    features = [
        {
            "type": "Feature",
            "properties": {"id": row.id, "muni_code": row.muni_code, "name": row.name},
            "geometry": row.geometry,
        }
        for row in rows
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
    )


@router.get("/comarcas/geojson", response_class=Response)
async def get_comarcas(
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return all comarca boundaries as GeoJSON."""
    result = await db.execute(
        text("""
            SELECT id, comarca_code, name,
                   ST_AsGeoJSON(geom)::json AS geometry
            FROM comarcas
            WHERE tenant_id = :tid
            ORDER BY name
        """),
        {"tid": tenant.tenant_id},
    )
    rows = result.fetchall()

    features = [
        {
            "type": "Feature",
            "properties": {"id": row.id, "comarca_code": row.comarca_code, "name": row.name},
            "geometry": row.geometry,
        }
        for row in rows
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
    )


@router.get("/nucleos/geojson", response_class=Response)
async def get_nucleos(
    include_diseminado: bool = Query(
        False, description="Include dispersed (diseminado) areas (nucleo_num=99)"
    ),
    tenant: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return EUSTAT núcleo (settlement) boundaries as GeoJSON."""
    where = "tenant_id = :tid"
    if not include_diseminado:
        where += " AND nucleo_num != '99'"

    result = await db.execute(
        text(f"""
            SELECT id, code, nucleo_num, name, entity_name,
                   muni_code, muni_name,
                   ST_AsGeoJSON(geom)::json AS geometry
            FROM nucleos
            WHERE {where}
            ORDER BY muni_name, name
        """),
        {"tid": tenant.tenant_id},
    )
    rows = result.fetchall()

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
            "geometry": row.geometry,
        }
        for row in rows
    ]

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}),
        media_type="application/geo+json",
    )
