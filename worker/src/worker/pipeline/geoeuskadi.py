"""Fetch real destination and boundary data from GeoEuskadi ArcGIS REST services.

All endpoints are public, no authentication required.
Geometries are requested in EPSG:4326 (WGS84) for direct storage.

Output: GeoParquet files in the serving directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import httpx
import pandas as pd
import structlog
from shapely.geometry import MultiLineString, MultiPolygon, Point, Polygon, shape

logger = structlog.get_logger()

# ── ArcGIS REST query endpoints ──

GEOEUSKADI_BASE = "https://www.geo.euskadi.eus/geoeuskadi/rest/services"

# Municipalities: layer 10, filter by MUN_PROV='48' (Bizkaia)
MUNICIPALITIES_URL = f"{GEOEUSKADI_BASE}/U11/LIMITES_CAS/MapServer/10/query"

# Schools: layer 1
SCHOOLS_URL = f"{GEOEUSKADI_BASE}/C06GIS/EDUCACION_CAS/MapServer/1/query"

# Health: pharmacies (layer 121) + health centres (layer 9)
PHARMACIES_URL = f"{GEOEUSKADI_BASE}/U11/SALUD_CAS/MapServer/121/query"
HEALTH_CENTRES_URL = f"{GEOEUSKADI_BASE}/U11/SALUD_CAS/MapServer/9/query"

# Supermarkets: layer 33 (grandes superficies / supermercados)
SUPERMARKETS_URL = f"{GEOEUSKADI_BASE}/DGSGIS/EUSTAT_CAS/MapServer/33/query"

# Economic activity areas: layer 7 (has geometry, unlike group layer 6)
EMPLOYMENT_ZONES_URL = f"{GEOEUSKADI_BASE}/DGSGIS/EUSTAT_CAS/MapServer/7/query"

# Bizkaia territory boundary: layer 7 (Territorio Historico)
TERRITORY_URL = f"{GEOEUSKADI_BASE}/U11/LIMITES_CAS/MapServer/7/query"

# Comarcas: layer 9, filter by COM_PROV='48' (Bizkaia)
COMARCAS_URL = f"{GEOEUSKADI_BASE}/U11/LIMITES_CAS/MapServer/9/query"

# Default request timeout
TIMEOUT_S = 60
MAX_RECORD_COUNT = 2000

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
    # Legacy types kept for backward compatibility
    {"code": "school_primary", "label": "School Primary", "description": "Primary schools"},
    {"code": "health_gp", "label": "Health GP", "description": "GPs / health centres / pharmacies"},
    {"code": "supermarket", "label": "Supermarket", "description": "Supermarkets"},
    {"code": "jobs", "label": "Jobs", "description": "Employment zones"},
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
    """Execute an ArcGIS REST query and return the JSON response."""
    params = {
        "where": where,
        "outFields": out_fields,
        "outSR": out_sr,
        "f": "geojson",
        "resultOffset": result_offset,
        "resultRecordCount": max_records,
    }
    with httpx.Client(timeout=TIMEOUT_S, verify=False) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


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


def _dest_type_id(code: str) -> int:
    """Look up a destination_type id by code from the static list."""
    for i, dt in enumerate(DESTINATION_TYPES, start=1):
        if dt["code"] == code:
            return i
    raise ValueError(f"Destination type '{code}' not found in DESTINATION_TYPES")


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


# ── Destination imports ──


def import_schools(tenant_id: str, serving_dir: str | Path) -> int:
    """Import primary schools in Bizkaia from GeoEuskadi education service.

    Appends to destinations.parquet.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("schools_import_start")

    type_id = _dest_type_id("school_primary")

    # Query schools in Bizkaia
    features = _query_all_features(
        SCHOOLS_URL,
        where="PROVINCIA='BIZKAIA' OR PROVINCIA='Bizkaia' OR PROV='48' OR TERRITORIO='48'",
    )

    if not features:
        # Fallback: get all schools and filter by bbox
        features = _query_all_features(SCHOOLS_URL)
        features = _filter_bizkaia_bbox(features)

    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        name = props.get("NOMBRE", props.get("IZENA_NOMBRE", f"School {len(records) + 1}"))

        records.append({
            "tenant_id": tenant_id,
            "type_id": type_id,
            "name": name,
            "weight": 1.0,
            "metadata": json.dumps({
                "source": "geoeuskadi",
                "class": props.get("CLASE_CENTRO", ""),
            }),
        })
        geometries.append(Point(coords[0], coords[1]))

    count = len(records)
    if records:
        gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
        _append_destinations(gdf, serving)

    log.info("schools_import_complete", count=count)
    return count


def import_health(tenant_id: str, serving_dir: str | Path) -> int:
    """Import health centres and pharmacies in Bizkaia from GeoEuskadi."""
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("health_import_start")

    type_id = _dest_type_id("health_gp")

    all_features: list[dict[str, Any]] = []

    # Health centres
    centres = _query_all_features(HEALTH_CENTRES_URL)
    centres = _filter_bizkaia_bbox(centres)
    all_features.extend(centres)

    # Pharmacies
    pharmacies = _query_all_features(
        PHARMACIES_URL,
        where="PROVINCIA='BIZKAIA'",
    )
    all_features.extend(pharmacies)

    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

    for f in all_features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        name = props.get("NOMBRE", props.get("TITULAR1", props.get("DENOM_C", f"Health {len(records) + 1}")))

        records.append({
            "tenant_id": tenant_id,
            "type_id": type_id,
            "name": name,
            "weight": 1.0,
            "metadata": json.dumps({"source": "geoeuskadi"}),
        })
        geometries.append(Point(coords[0], coords[1]))

    count = len(records)
    if records:
        gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
        _append_destinations(gdf, serving)

    log.info("health_import_complete", count=count)
    return count


def import_supermarkets(tenant_id: str, serving_dir: str | Path) -> int:
    """Import supermarkets in Bizkaia from EUSTAT ArcGIS service."""
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("supermarkets_import_start")

    type_id = _dest_type_id("supermarket")

    features = _query_all_features(SUPERMARKETS_URL)
    features = _filter_bizkaia_bbox(features)

    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        name = props.get("DENOM_C", props.get("NOMBRE", f"Supermarket {len(records) + 1}"))

        records.append({
            "tenant_id": tenant_id,
            "type_id": type_id,
            "name": name,
            "weight": 1.0,
            "metadata": json.dumps({
                "source": "geoeuskadi_eustat",
                "cnae": props.get("CNAE", ""),
            }),
        })
        geometries.append(Point(coords[0], coords[1]))

    count = len(records)
    if records:
        gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
        _append_destinations(gdf, serving)

    log.info("supermarkets_import_complete", count=count)
    return count


def import_jobs(tenant_id: str, serving_dir: str | Path) -> int:
    """Import employment zones (business parks) in Bizkaia from EUSTAT.

    Uses polygon centroids as destination points, weighted by area.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("jobs_import_start")

    type_id = _dest_type_id("jobs")

    features = _query_all_features(EMPLOYMENT_ZONES_URL)
    features = _filter_bizkaia_bbox(features)

    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

    for f in features:
        props = f.get("properties", {})
        geom_json = f.get("geometry")
        if not geom_json:
            continue

        name = props.get("GAE_DS_C", props.get("DENOM_C", props.get("NOMBRE", f"Employment zone {len(records) + 1}")))

        # Use centroid for polygon geometries
        geom_shape = shape(geom_json)
        centroid = geom_shape.centroid

        records.append({
            "tenant_id": tenant_id,
            "type_id": type_id,
            "name": name,
            "weight": 1.0,
            "metadata": json.dumps({
                "source": "geoeuskadi_eustat",
                "code": props.get("GAE_CODAE", ""),
            }),
        })
        geometries.append(centroid)

    count = len(records)
    if records:
        gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
        _append_destinations(gdf, serving)

    log.info("jobs_import_complete", count=count)
    return count


# ── Helpers ──


def _append_destinations(new_gdf: gpd.GeoDataFrame, serving: Path) -> None:
    """Append new destinations to the existing destinations.parquet, or create it."""
    dest_path = serving / "destinations.parquet"
    if dest_path.exists():
        existing = gpd.read_parquet(dest_path)
        combined = pd.concat([existing, new_gdf], ignore_index=True)
        combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    else:
        combined = new_gdf
    _write_geoparquet(combined, dest_path)


def _filter_bizkaia_bbox(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter GeoJSON features to those within the Bizkaia bounding box.

    Approximate Bizkaia extent in WGS84:
    lon: -3.45 to -2.40, lat: 43.05 to 43.45
    """
    filtered = []
    for f in features:
        geom = f.get("geometry")
        if not geom:
            continue
        coords = geom.get("coordinates")
        if not coords:
            continue

        # Get a representative point
        if geom["type"] == "Point":
            lon, lat = coords[0], coords[1]
        elif geom["type"] in ("Polygon", "MultiPolygon"):
            # Use first coordinate of first ring
            ring = coords[0] if geom["type"] == "Polygon" else coords[0][0]
            if not ring:
                continue
            lon, lat = ring[0][0], ring[0][1]
        else:
            continue

        if -3.45 <= lon <= -2.40 and 43.05 <= lat <= 43.45:
            filtered.append(f)

    return filtered
