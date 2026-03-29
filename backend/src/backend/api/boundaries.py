"""Boundary GeoJSON endpoints: region, municipalities, comarcas."""

import json

from fastapi import APIRouter, Depends
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
