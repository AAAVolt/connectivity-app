"""Generate synthetic demo data for local development.

Creates dummy destinations and distance-based travel times so the full
pipeline (grid -> population -> travel times -> scores) can run without
real OSM/GTFS data or the R5R routing container.

Generates travel times for multiple departure time slots to demonstrate
time-of-day variation in accessibility.

Output: destinations.parquet + travel_times.parquet in the serving directory.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import structlog
from shapely.geometry import Point

logger = structlog.get_logger()

# Demo boundary centre and extent (matches 002_seed_demo.sql)
# POLYGON((-2.97 43.24, -2.97 43.29, -2.90 43.29, -2.90 43.24, ...))
BOUNDARY_LON_MIN, BOUNDARY_LON_MAX = -2.97, -2.90
BOUNDARY_LAT_MIN, BOUNDARY_LAT_MAX = 43.24, 43.29

# Approximate transit speed for synthetic travel times
TRANSIT_SPEED_KMH = 15.0
TRANSIT_WAIT_MIN = 5.0
MAX_TRAVEL_TIME = 60.0

# Departure time slots for demo: every 30 min across the day (48 slots)
DEMO_DEPARTURE_SLOTS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]

# Time-of-day multipliers for transit speed and wait time.
# Simulates: frequent peak service, moderate midday, sparse night.
_TRANSIT_TIME_MULTIPLIERS: dict[str, tuple[float, float]] = {}
for _h in range(24):
    for _m in (0, 30):
        _slot = f"{_h:02d}:{_m:02d}"
        if 7 <= _h <= 9:
            # AM peak: fast, short waits
            _TRANSIT_TIME_MULTIPLIERS[_slot] = (1.0, 1.0)
        elif 17 <= _h <= 19:
            # PM peak: fast, short waits
            _TRANSIT_TIME_MULTIPLIERS[_slot] = (1.0, 1.0)
        elif 10 <= _h <= 16:
            # Midday: slightly slower, moderate waits
            _TRANSIT_TIME_MULTIPLIERS[_slot] = (1.15, 1.5)
        elif 20 <= _h <= 22:
            # Evening: slower, longer waits
            _TRANSIT_TIME_MULTIPLIERS[_slot] = (1.3, 2.5)
        else:
            # Night (23:00 - 06:30): much slower / no service
            _TRANSIT_TIME_MULTIPLIERS[_slot] = (2.0, 4.0)


# Destination type code -> id mapping (must match destination_types.parquet)
# These IDs correspond to the DESTINATION_TYPES list in geoeuskadi.py
DEST_TYPE_IDS: dict[str, int] = {
    "centro_educativo": 3,
    "consulta_general": 5,
    "hospital": 7,
    "osakidetza": 8,
}

# Synthetic destination locations within the Bilbao demo area
# (lon, lat, name) tuples grouped by destination type code
DEMO_DESTINATIONS: dict[str, list[tuple[float, float, str]]] = {
    "centro_educativo": [
        (-2.938, 43.262, "CEIP Cervantes"),
        (-2.948, 43.272, "CEIP Deusto"),
        (-2.922, 43.261, "CEIP Casco Viejo"),
        (-2.955, 43.278, "CEIP San Ignacio"),
        (-2.935, 43.263, "IES Abando"),
        (-2.945, 43.265, "IES Gran Via"),
        (-2.924, 43.260, "IES Casco Viejo"),
        (-2.930, 43.255, "Colegio Atxuri"),
    ],
    "consulta_general": [
        (-2.934, 43.264, "Centro de Salud Abando"),
        (-2.920, 43.259, "Ambulatorio Casco Viejo"),
        (-2.952, 43.274, "Centro de Salud Deusto"),
    ],
    "hospital": [
        (-2.937, 43.266, "Hospital de Basurto"),
        (-2.925, 43.260, "Hospital de Cruces"),
        (-2.953, 43.273, "Hospital de Galdakao"),
    ],
    "osakidetza": [
        (-2.942, 43.258, "Osakidetza Indautxu"),
        (-2.960, 43.276, "Osakidetza San Ignacio"),
        (-2.950, 43.275, "Osakidetza Deusto"),
        (-2.940, 43.270, "Osakidetza Zorrotzaurre"),
        (-2.915, 43.257, "Osakidetza Bilbao La Vieja"),
    ],
}


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def seed_destinations(tenant_id: str, serving_dir: str | Path) -> int:
    """Write synthetic destinations for all four purpose types.

    Writes destinations.parquet as GeoParquet (overwrites existing).
    Returns the number of destinations created.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id)

    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

    for type_code, locations in DEMO_DESTINATIONS.items():
        type_id = DEST_TYPE_IDS[type_code]

        for lon, lat, name in locations:
            records.append({
                "tenant_id": tenant_id,
                "type_id": type_id,
                "name": name,
                "weight": 1.0,
                "metadata": "{}",
            })
            geometries.append(Point(lon, lat))

    gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
    gdf["id"] = range(1, len(gdf) + 1)
    out_path = serving / "destinations.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(out_path)

    count = len(records)
    log.info("seed_destinations_complete", count=count)
    return count


def seed_travel_times(
    tenant_id: str,
    serving_dir: str | Path,
    *,
    sample_fraction: float = 1.0,
) -> dict[str, int]:
    """Generate synthetic travel times based on straight-line distance.

    For each (grid_cell, destination, mode, departure_time) combination,
    computes an approximate travel time using haversine distance and
    mode-specific speeds with time-of-day variation.

    Reads grid_cells.parquet and destinations.parquet from serving_dir.
    Writes travel_times.parquet.

    Args:
        sample_fraction: Fraction of cells to process (0-1). Use < 1.0
            to speed up seeding on large grids.

    Returns dict with counts per mode.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id)
    log.info("seed_travel_times_start")

    # Read grid cells
    grid_path = serving / "grid_cells.parquet"
    if not grid_path.exists():
        raise ValueError("No grid_cells.parquet found -- run build-grid first")

    grid_gdf = gpd.read_parquet(grid_path)
    grid_gdf = grid_gdf[grid_gdf["tenant_id"] == tenant_id].copy()

    if grid_gdf.empty:
        raise ValueError("No grid cells found for tenant -- run build-grid first")

    # Extract cell centroids — geometry column may be named 'geom'
    geo_col = grid_gdf.geometry.name  # active geometry column name
    cells: list[tuple[int, float, float]] = []
    for _, row in grid_gdf.iterrows():
        cell_id = row.get("id", row.name)
        geom = row[geo_col]
        centroid = geom.centroid if hasattr(geom, "centroid") else geom
        cells.append((int(cell_id), centroid.x, centroid.y))

    # Optionally sample cells for faster seeding
    if sample_fraction < 1.0:
        rng = random.Random(42)
        k = max(1, int(len(cells) * sample_fraction))
        cells = rng.sample(cells, k)

    # Read destinations
    dest_path = serving / "destinations.parquet"
    if not dest_path.exists():
        raise ValueError("No destinations.parquet found -- run seed-destinations first")

    dest_gdf = gpd.read_parquet(dest_path)
    dest_gdf = dest_gdf[dest_gdf["tenant_id"] == tenant_id].copy()

    if dest_gdf.empty:
        raise ValueError("No destinations found -- run seed-destinations first")

    dest_geo_col = dest_gdf.geometry.name
    dests: list[tuple[int, float, float]] = []
    for _, row in dest_gdf.iterrows():
        dest_id = row.get("id", row.name)
        pt = row[dest_geo_col]
        dests.append((int(dest_id), pt.x, pt.y))

    # Generate travel times (TRANSIT only)
    rows: list[dict[str, object]] = []
    counts: dict[str, int] = {"TRANSIT": 0}

    for cell_id, cell_lon, cell_lat in cells:
        for dest_id, dest_lon, dest_lat in dests:
            dist_km = _haversine_km(cell_lon, cell_lat, dest_lon, dest_lat)

            for slot in DEMO_DEPARTURE_SLOTS:
                speed_mult, wait_mult = _TRANSIT_TIME_MULTIPLIERS[slot]
                jitter = 0.85 + (hash((cell_id, dest_id, "TRANSIT")) % 31) / 100.0
                transit_min = (
                    dist_km / TRANSIT_SPEED_KMH * 60.0 * speed_mult
                    + TRANSIT_WAIT_MIN * wait_mult
                ) * jitter

                if transit_min <= MAX_TRAVEL_TIME:
                    transit_min = round(max(1.0, transit_min), 1)
                    rows.append({
                        "tenant_id": tenant_id,
                        "origin_cell_id": cell_id,
                        "destination_id": dest_id,
                        "mode": "TRANSIT",
                        "departure_time": slot,
                        "travel_time_minutes": transit_min,
                    })
                    counts["TRANSIT"] += 1

    # Write to Parquet
    if rows:
        df = pd.DataFrame(rows)
        out_path = serving / "travel_times.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, index=False)

    log.info("seed_travel_times_complete", **counts)
    return counts
