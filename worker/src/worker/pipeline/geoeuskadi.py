"""Fetch real destination and boundary data from GeoEuskadi ArcGIS REST services.

All endpoints are public, no authentication required.
Geometries are requested in EPSG:4326 (WGS84) for direct storage.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

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


# ── Boundary import ──


def import_bizkaia_boundary(session: Session, tenant_id: str) -> int:
    """Import the full Bizkaia territory boundary from GeoEuskadi.

    Replaces the demo boundary with the real territorial boundary.
    Returns 1 on success.
    """
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

    # Use the first matching feature
    geojson_geom = json.dumps(features[0]["geometry"])

    # Clear existing boundaries and insert the real one
    session.execute(
        text("DELETE FROM boundaries WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )

    session.execute(
        text("""
            INSERT INTO boundaries (tenant_id, name, boundary_type, geom)
            VALUES (
                :tid, 'Bizkaia', 'region',
                ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
            )
        """),
        {"tid": tenant_id, "geom": geojson_geom},
    )
    session.commit()

    log.info("boundary_import_complete", features=len(features))
    return 1


def import_municipalities(session: Session, tenant_id: str) -> int:
    """Import all Bizkaia municipalities from GeoEuskadi.

    Returns the number of municipalities imported.
    """
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("municipalities_import_start")

    features = _query_all_features(
        MUNICIPALITIES_URL,
        where="MUN_PROV='48'",
    )

    if not features:
        raise ValueError("No Bizkaia municipalities found in GeoEuskadi")

    # Clear existing
    session.execute(
        text("DELETE FROM municipalities WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )

    count = 0
    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom:
            continue

        muni_code = str(props.get("EUSTAT", props.get("OBJECTID", "")))
        name = props.get("NOMBRE_CAS", props.get("NOMBRE_TOP", f"Municipality {muni_code}"))

        session.execute(
            text("""
                INSERT INTO municipalities (tenant_id, muni_code, name, geom)
                VALUES (
                    :tid, :muni_code, :name,
                    ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
                )
                ON CONFLICT (tenant_id, muni_code) DO UPDATE
                SET name = EXCLUDED.name, geom = EXCLUDED.geom
            """),
            {
                "tid": tenant_id,
                "muni_code": muni_code,
                "name": name,
                "geom": json.dumps(geom),
            },
        )
        count += 1

    session.commit()
    log.info("municipalities_import_complete", count=count)
    return count


def import_comarcas(session: Session, tenant_id: str) -> int:
    """Import all Bizkaia comarcas from GeoEuskadi.

    Returns the number of comarcas imported.
    """
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("comarcas_import_start")

    features = _query_all_features(
        COMARCAS_URL,
        where="COM_PROV='48'",
    )

    if not features:
        raise ValueError("No Bizkaia comarcas found in GeoEuskadi")

    # Clear existing
    session.execute(
        text("DELETE FROM comarcas WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )

    count = 0
    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom:
            continue

        comarca_code = str(props.get("COM_COM", props.get("OBJECTID", "")))
        name = props.get("COMARCA", f"Comarca {comarca_code}")

        session.execute(
            text("""
                INSERT INTO comarcas (tenant_id, comarca_code, name, geom)
                VALUES (
                    :tid, :comarca_code, :name,
                    ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
                )
                ON CONFLICT (tenant_id, comarca_code) DO UPDATE
                SET name = EXCLUDED.name, geom = EXCLUDED.geom
            """),
            {
                "tid": tenant_id,
                "comarca_code": comarca_code,
                "name": name,
                "geom": json.dumps(geom),
            },
        )
        count += 1

    session.commit()
    log.info("comarcas_import_complete", count=count)
    return count


# ── Destination imports ──


def _dest_type_id(session: Session, code: str) -> int:
    """Look up a destination_type id by code."""
    result = session.execute(
        text("SELECT id FROM destination_types WHERE code = :code"),
        {"code": code},
    ).scalar_one_or_none()
    if result is None:
        raise ValueError(f"Destination type '{code}' not found in DB")
    return result


def import_schools(session: Session, tenant_id: str) -> int:
    """Import primary schools in Bizkaia from GeoEuskadi education service.

    Filters by province code '48' (Bizkaia) and primary school types.
    """
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("schools_import_start")

    type_id = _dest_type_id(session, "school_primary")

    # Query schools in Bizkaia — try province filter
    features = _query_all_features(
        SCHOOLS_URL,
        where="PROVINCIA='BIZKAIA' OR PROVINCIA='Bizkaia' OR PROV='48' OR TERRITORIO='48'",
    )

    if not features:
        # Fallback: get all schools and filter by bbox (Bizkaia approx bounds)
        features = _query_all_features(SCHOOLS_URL)
        features = _filter_bizkaia_bbox(features)

    # Clear existing schools for this tenant
    session.execute(
        text("DELETE FROM destinations WHERE tenant_id = :tid AND type_id = :type_id"),
        {"tid": tenant_id, "type_id": type_id},
    )

    count = 0
    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        name = props.get("NOMBRE", props.get("IZENA_NOMBRE", f"School {count + 1}"))

        session.execute(
            text("""
                INSERT INTO destinations (tenant_id, type_id, name, geom, weight, metadata)
                VALUES (
                    :tid, :type_id, :name,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    1.0, :meta
                )
            """),
            {
                "tid": tenant_id,
                "type_id": type_id,
                "name": name,
                "lon": coords[0],
                "lat": coords[1],
                "meta": json.dumps({
                    "source": "geoeuskadi",
                    "class": props.get("CLASE_CENTRO", ""),
                }),
            },
        )
        count += 1

    session.commit()
    log.info("schools_import_complete", count=count)
    return count


def import_health(session: Session, tenant_id: str) -> int:
    """Import health centres and pharmacies in Bizkaia from GeoEuskadi."""
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("health_import_start")

    type_id = _dest_type_id(session, "health_gp")

    all_features: list[dict[str, Any]] = []

    # Health centres (layer uses TH field for territory)
    centres = _query_all_features(HEALTH_CENTRES_URL)
    centres = _filter_bizkaia_bbox(centres)
    all_features.extend(centres)

    # Pharmacies (PROVINCIA field)
    pharmacies = _query_all_features(
        PHARMACIES_URL,
        where="PROVINCIA='BIZKAIA'",
    )
    all_features.extend(pharmacies)

    # Clear existing
    session.execute(
        text("DELETE FROM destinations WHERE tenant_id = :tid AND type_id = :type_id"),
        {"tid": tenant_id, "type_id": type_id},
    )

    count = 0
    for f in all_features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        name = props.get("NOMBRE", props.get("TITULAR1", props.get("DENOM_C", f"Health {count + 1}")))

        session.execute(
            text("""
                INSERT INTO destinations (tenant_id, type_id, name, geom, weight, metadata)
                VALUES (
                    :tid, :type_id, :name,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    1.0, :meta
                )
            """),
            {
                "tid": tenant_id,
                "type_id": type_id,
                "name": name,
                "lon": coords[0],
                "lat": coords[1],
                "meta": json.dumps({"source": "geoeuskadi"}),
            },
        )
        count += 1

    session.commit()
    log.info("health_import_complete", count=count)
    return count


def import_supermarkets(session: Session, tenant_id: str) -> int:
    """Import supermarkets in Bizkaia from EUSTAT ArcGIS service."""
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("supermarkets_import_start")

    type_id = _dest_type_id(session, "supermarket")

    features = _query_all_features(SUPERMARKETS_URL)
    features = _filter_bizkaia_bbox(features)

    # Clear existing
    session.execute(
        text("DELETE FROM destinations WHERE tenant_id = :tid AND type_id = :type_id"),
        {"tid": tenant_id, "type_id": type_id},
    )

    count = 0
    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        name = props.get("DENOM_C", props.get("NOMBRE", f"Supermarket {count + 1}"))

        session.execute(
            text("""
                INSERT INTO destinations (tenant_id, type_id, name, geom, weight, metadata)
                VALUES (
                    :tid, :type_id, :name,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    1.0, :meta
                )
            """),
            {
                "tid": tenant_id,
                "type_id": type_id,
                "name": name,
                "lon": coords[0],
                "lat": coords[1],
                "meta": json.dumps({
                    "source": "geoeuskadi_eustat",
                    "cnae": props.get("CNAE", ""),
                }),
            },
        )
        count += 1

    session.commit()
    log.info("supermarkets_import_complete", count=count)
    return count


def import_jobs(session: Session, tenant_id: str) -> int:
    """Import employment zones (business parks) in Bizkaia from EUSTAT.

    Uses polygon centroids as destination points, weighted by area.
    """
    log = logger.bind(tenant_id=tenant_id, source="geoeuskadi")
    log.info("jobs_import_start")

    type_id = _dest_type_id(session, "jobs")

    features = _query_all_features(EMPLOYMENT_ZONES_URL)
    features = _filter_bizkaia_bbox(features)

    # Clear existing
    session.execute(
        text("DELETE FROM destinations WHERE tenant_id = :tid AND type_id = :type_id"),
        {"tid": tenant_id, "type_id": type_id},
    )

    count = 0
    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry")
        if not geom:
            continue

        geom_json = json.dumps(geom)

        name = props.get("GAE_DS_C", props.get("DENOM_C", props.get("NOMBRE", f"Employment zone {count + 1}")))

        # Insert using ST_Centroid for polygon geometries
        session.execute(
            text("""
                INSERT INTO destinations (tenant_id, type_id, name, geom, weight, metadata)
                VALUES (
                    :tid, :type_id, :name,
                    ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)),
                    1.0, :meta
                )
            """),
            {
                "tid": tenant_id,
                "type_id": type_id,
                "name": name,
                "geom": geom_json,
                "meta": json.dumps({
                    "source": "geoeuskadi_eustat",
                    "code": props.get("GAE_CODAE", ""),
                }),
            },
        )
        count += 1

    session.commit()
    log.info("jobs_import_complete", count=count)
    return count


# ── Helpers ──


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
