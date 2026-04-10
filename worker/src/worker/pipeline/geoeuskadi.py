"""Fetch real destination and boundary data from GeoEuskadi ArcGIS REST services.

All endpoints are public, no authentication required.
Geometries are requested in EPSG:4326 (WGS84) for direct storage.

Output: GeoParquet files in the serving directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import os
import time

import geopandas as gpd
import httpx
import pandas as pd
import structlog
from shapely.geometry import MultiLineString, MultiPolygon, Polygon, shape

# Allow disabling SSL verification only when explicitly opted in (e.g. dev with
# corporate proxy). Default is to verify certificates.
_VERIFY_SSL = os.environ.get("GEOEUSKADI_VERIFY_SSL", "1").lower() not in ("0", "false", "no")

logger = structlog.get_logger()

# ── ArcGIS REST query endpoints ──

GEOEUSKADI_BASE = "https://www.geo.euskadi.eus/geoeuskadi/rest/services"

# Municipalities: layer 10, filter by MUN_PROV='48' (Bizkaia)
MUNICIPALITIES_URL = f"{GEOEUSKADI_BASE}/U11/LIMITES_CAS/MapServer/10/query"

# Bizkaia territory boundary: layer 7 (Territorio Historico)
TERRITORY_URL = f"{GEOEUSKADI_BASE}/U11/LIMITES_CAS/MapServer/7/query"

# Comarcas: layer 9, filter by COM_PROV='48' (Bizkaia)
COMARCAS_URL = f"{GEOEUSKADI_BASE}/U11/LIMITES_CAS/MapServer/9/query"

# Default request timeout
TIMEOUT_S = 60
MAX_RECORD_COUNT = 2000
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0

# Destination type definitions (from 002_seed_demo.sql)
DESTINATION_TYPES = [
    {"code": "aeropuerto", "label": "Aeropuerto", "description": "Airports"},
    {"code": "bachiller", "label": "Bachiller", "description": "Secondary / vocational schools (BHI)"},
    {"code": "centro_educativo", "label": "Centro Educativo", "description": "Education centres"},
    {"code": "centro_urbano", "label": "Centro Urbano", "description": "Urban centres"},
    {"code": "consulta_general", "label": "Consulta General", "description": "GP / general health consultations"},
    {"code": "hacienda", "label": "Hacienda", "description": "Government tax / finance offices"},
    {"code": "hospital", "label": "Hospital", "description": "Hospitals"},
    {"code": "osakidetza", "label": "Osakidetza", "description": "Osakidetza health service locations"},
    {"code": "residencia", "label": "Residencia", "description": "Residential care facilities"},
    {"code": "universidad", "label": "Universidad", "description": "Universities"},
]


def _query_arcgis(
    url: str,
    where: str = "1=1",
    out_fields: str = "*",
    *,
    out_sr: int = 4326,
    result_offset: int = 0,
    max_records: int = MAX_RECORD_COUNT,
) -> dict[str, Any]:
    """Execute an ArcGIS REST query and return the JSON response.

    Retries up to ``_MAX_RETRIES`` times with exponential back-off on
    transient network / server errors.
    """
    params = {
        "where": where,
        "outFields": out_fields,
        "outSR": out_sr,
        "f": "geojson",
        "resultOffset": result_offset,
        "resultRecordCount": max_records,
    }
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_S, verify=_VERIFY_SSL) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise  # Client errors (4xx) are not retryable
            delay = _RETRY_BACKOFF_S * (2 ** (attempt - 1))
            logger.warning(
                "arcgis_query_retry",
                url=url,
                attempt=attempt,
                max_retries=_MAX_RETRIES,
                delay_s=delay,
                error=str(exc),
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _query_all_features(
    url: str,
    where: str = "1=1",
    out_fields: str = "*",
) -> list[dict[str, Any]]:
    """Page through all results from an ArcGIS REST endpoint."""
    all_features: list[dict[str, Any]] = []
    offset = 0
    while True:
        data = _query_arcgis(url, where, out_fields, result_offset=offset)
        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        if len(features) < MAX_RECORD_COUNT:
            break
        offset += len(features)
    return all_features


def _ensure_multi(geom: Any) -> MultiPolygon:
    """Promote Polygon to MultiPolygon for schema consistency."""
    if geom is None:
        return MultiPolygon()
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    # GeometryCollection — extract polygon parts
    polys: list[Polygon] = []
    for g in getattr(geom, "geoms", []):
        if isinstance(g, Polygon):
            polys.append(g)
        elif isinstance(g, MultiPolygon):
            polys.extend(g.geoms)
    return MultiPolygon(polys) if polys else MultiPolygon()


def _write_geoparquet(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """Write a GeoDataFrame to GeoParquet, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(path)


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to Parquet, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


# ── Seed data helpers ──


def seed_tenants_and_modes(serving_dir: str | Path) -> None:
    """Write tenants.parquet and modes.parquet with default demo data."""
    serving = Path(serving_dir)
    log = logger.bind(serving_dir=str(serving))

    # Tenants
    tenants_df = pd.DataFrame([{
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "Bizkaia Demo",
        "slug": "bizkaia-demo",
        "config": '{"region": "bizkaia", "crs_projected": 25830}',
    }])
    _write_parquet(tenants_df, serving / "tenants.parquet")
    log.info("tenants_written", count=len(tenants_df))

    # Modes
    modes_df = pd.DataFrame([
        {"id": 1, "code": "TRANSIT", "label": "Public Transport"},
    ])
    _write_parquet(modes_df, serving / "modes.parquet")
    log.info("modes_written", count=len(modes_df))

    # Destination types
    dest_types_df = pd.DataFrame(DESTINATION_TYPES)
    dest_types_df.insert(0, "id", range(1, len(dest_types_df) + 1))
    _write_parquet(dest_types_df, serving / "destination_types.parquet")
    log.info("destination_types_written", count=len(dest_types_df))



# ── Boundary import ──


def import_bizkaia_boundary(tenant_id: str, serving_dir: str | Path) -> int:
    """Import the full Bizkaia territory boundary from GeoEuskadi.

    Writes boundaries.parquet as GeoParquet.
    Returns 1 on success.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("boundary_import_start")

    # Fetch Bizkaia territory (CODIGO='48' or NOMBRE like 'Bizkaia')
    features = _query_all_features(
        TERRITORY_URL,
        where="CODIGO='48' OR NOMBRE_CAS LIKE '%Bizkaia%' OR NOMBRE_CAS LIKE '%Vizcaya%'",
    )

    if not features:
        # Fallback: try fetching all territories and filter
        features = _query_all_features(TERRITORY_URL)
        features = [
            f for f in features
            if "bizkaia" in json.dumps(f.get("properties", {})).lower()
            or "vizcaya" in json.dumps(f.get("properties", {})).lower()
        ]

    if not features:
        raise ValueError("Could not find Bizkaia boundary in GeoEuskadi")

    # Build GeoDataFrame
    geom = shape(features[0]["geometry"])
    geom = _ensure_multi(geom)

    gdf = gpd.GeoDataFrame(
        [{
            "tenant_id": tenant_id,
            "name": "Bizkaia",
            "boundary_type": "region",
        }],
        geometry=[geom],
        crs="EPSG:4326",
    )

    _write_geoparquet(gdf, serving / "boundaries.parquet")

    log.info("boundary_import_complete", features=len(features))
    return 1


def import_municipalities(tenant_id: str, serving_dir: str | Path) -> int:
    """Import all Bizkaia municipalities from GeoEuskadi.

    Writes municipalities.parquet as GeoParquet.
    Returns the number of municipalities imported.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("municipalities_import_start")

    features = _query_all_features(
        MUNICIPALITIES_URL,
        where="MUN_PROV='48'",
    )

    if not features:
        raise ValueError("No Bizkaia municipalities found in GeoEuskadi")

    records: list[dict[str, Any]] = []
    geometries: list[Any] = []

    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom:
            continue

        muni_code = str(props.get("EUSTAT", props.get("OBJECTID", "")))
        name = props.get("NOMBRE_CAS", props.get("NOMBRE_TOP", f"Municipality {muni_code}"))

        geom_shape = shape(geom)
        geom_shape = _ensure_multi(geom_shape)

        records.append({
            "tenant_id": tenant_id,
            "muni_code": muni_code,
            "name": name,
        })
        geometries.append(geom_shape)

    gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
    _write_geoparquet(gdf, serving / "municipalities.parquet")

    count = len(records)
    log.info("municipalities_import_complete", count=count)
    return count


def import_comarcas(tenant_id: str, serving_dir: str | Path) -> int:
    """Import all Bizkaia comarcas from GeoEuskadi.

    Writes comarcas.parquet as GeoParquet.
    Returns the number of comarcas imported.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("comarcas_import_start")

    features = _query_all_features(
        COMARCAS_URL,
        where="COM_PROV='48'",
    )

    if not features:
        raise ValueError("No Bizkaia comarcas found in GeoEuskadi")

    records: list[dict[str, Any]] = []
    geometries: list[Any] = []

    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom:
            continue

        comarca_code = str(props.get("COM_COM", props.get("OBJECTID", "")))
        name = props.get("COMARCA", f"Comarca {comarca_code}")

        geom_shape = shape(geom)
        geom_shape = _ensure_multi(geom_shape)

        records.append({
            "tenant_id": tenant_id,
            "comarca_code": comarca_code,
            "name": name,
        })
        geometries.append(geom_shape)

    gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
    _write_geoparquet(gdf, serving / "comarcas.parquet")

    count = len(records)
    log.info("comarcas_import_complete", count=count)
    return count


