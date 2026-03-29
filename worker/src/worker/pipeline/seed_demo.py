"""Generate synthetic demo data for local development.

Creates dummy destinations and distance-based travel times so the full
pipeline (grid → population → travel times → scores) can run without
real OSM/GTFS data or the R5R routing container.
"""

from __future__ import annotations

import math
import random

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# Demo boundary centre and extent (matches 002_seed_demo.sql)
# POLYGON((-2.97 43.24, -2.97 43.29, -2.90 43.29, -2.90 43.24, ...))
BOUNDARY_LON_MIN, BOUNDARY_LON_MAX = -2.97, -2.90
BOUNDARY_LAT_MIN, BOUNDARY_LAT_MAX = 43.24, 43.29

# Approximate walking/transit speeds for synthetic travel times
WALK_SPEED_KMH = 3.6
TRANSIT_SPEED_KMH = 15.0
TRANSIT_WAIT_MIN = 5.0
MAX_TRAVEL_TIME = 60.0

# Synthetic destination locations within the Bilbao demo area
# (lon, lat, name) tuples grouped by destination type code
DEMO_DESTINATIONS: dict[str, list[tuple[float, float, str]]] = {
    "jobs": [
        (-2.935, 43.263, "Abando Business District"),
        (-2.945, 43.265, "Gran Vía Office Park"),
        (-2.924, 43.260, "Casco Viejo Commerce"),
        (-2.950, 43.275, "Deusto University Campus"),
        (-2.915, 43.257, "Bilbao La Vieja Workshops"),
        (-2.940, 43.270, "Zorrotzaurre Tech Hub"),
        (-2.960, 43.275, "San Ignacio Retail Park"),
        (-2.930, 43.255, "Atxuri Logistics Centre"),
    ],
    "school_primary": [
        (-2.938, 43.262, "CEIP Cervantes"),
        (-2.948, 43.272, "CEIP Deusto"),
        (-2.922, 43.261, "CEIP Casco Viejo"),
        (-2.955, 43.278, "CEIP San Ignacio"),
    ],
    "health_gp": [
        (-2.934, 43.264, "Centro de Salud Abando"),
        (-2.920, 43.259, "Ambulatorio Casco Viejo"),
        (-2.952, 43.274, "Centro de Salud Deusto"),
    ],
    "supermarket": [
        (-2.937, 43.266, "Eroski Indautxu"),
        (-2.925, 43.260, "BM Casco Viejo"),
        (-2.953, 43.273, "Mercadona Deusto"),
        (-2.942, 43.258, "Carrefour Express Abando"),
        (-2.960, 43.276, "Eroski San Ignacio"),
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


def seed_destinations(session: Session, tenant_id: str) -> int:
    """Insert synthetic destinations for all four purpose types.

    Returns the number of destinations created.
    """
    log = logger.bind(tenant_id=tenant_id)

    # Clear existing destinations for this tenant
    session.execute(
        text("DELETE FROM destinations WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )

    count = 0
    for type_code, locations in DEMO_DESTINATIONS.items():
        # Look up the destination_type id
        type_id = session.execute(
            text("SELECT id FROM destination_types WHERE code = :code"),
            {"code": type_code},
        ).scalar_one()

        for lon, lat, name in locations:
            session.execute(
                text("""
                    INSERT INTO destinations (tenant_id, type_id, name, geom, weight)
                    VALUES (
                        :tid, :type_id, :name,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                        :weight
                    )
                """),
                {
                    "tid": tenant_id,
                    "type_id": type_id,
                    "name": name,
                    "lon": lon,
                    "lat": lat,
                    "weight": 1.0,
                },
            )
            count += 1

    session.commit()
    log.info("seed_destinations_complete", count=count)
    return count


def seed_travel_times(
    session: Session,
    tenant_id: str,
    *,
    sample_fraction: float = 1.0,
) -> dict[str, int]:
    """Generate synthetic travel times based on straight-line distance.

    For each (grid_cell, destination, mode) combination, computes an
    approximate travel time using haversine distance and mode-specific
    speeds.  Only pairs within the 60-minute cutoff are stored.

    Args:
        sample_fraction: Fraction of cells to process (0–1). Use < 1.0
            to speed up seeding on large grids.

    Returns dict with counts per mode.
    """
    log = logger.bind(tenant_id=tenant_id)
    log.info("seed_travel_times_start")

    # Clear existing travel times
    session.execute(
        text("DELETE FROM travel_times WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )

    # Fetch grid cell centroids
    cells = session.execute(
        text("""
            SELECT id, ST_X(centroid) AS lon, ST_Y(centroid) AS lat
            FROM grid_cells
            WHERE tenant_id = :tid
        """),
        {"tid": tenant_id},
    ).fetchall()

    if not cells:
        raise ValueError("No grid cells found — run build-grid first")

    # Optionally sample cells for faster seeding
    if sample_fraction < 1.0:
        rng = random.Random(42)
        k = max(1, int(len(cells) * sample_fraction))
        cells = rng.sample(cells, k)

    # Fetch destinations
    dests = session.execute(
        text("SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM destinations WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    ).fetchall()

    if not dests:
        raise ValueError("No destinations found — run seed-destinations first")

    modes = [
        ("WALK", WALK_SPEED_KMH, 0.0),
        ("TRANSIT", TRANSIT_SPEED_KMH, TRANSIT_WAIT_MIN),
    ]

    batch: list[dict[str, object]] = []
    counts: dict[str, int] = {"WALK": 0, "TRANSIT": 0}
    batch_size = 5000

    for cell_id, cell_lon, cell_lat in cells:
        for dest_id, dest_lon, dest_lat in dests:
            dist_km = _haversine_km(cell_lon, cell_lat, dest_lon, dest_lat)

            for mode, speed, wait in modes:
                # Add ±15% jitter for realism
                jitter = 0.85 + (hash((cell_id, dest_id, mode)) % 31) / 100.0
                travel_min = (dist_km / speed * 60.0 + wait) * jitter

                if travel_min > MAX_TRAVEL_TIME:
                    continue

                travel_min = round(max(1.0, travel_min), 1)

                batch.append({
                    "tenant_id": tenant_id,
                    "origin_cell_id": cell_id,
                    "destination_id": dest_id,
                    "mode": mode,
                    "travel_time_minutes": travel_min,
                })
                counts[mode] += 1

                if len(batch) >= batch_size:
                    _insert_batch(session, batch)
                    batch = []

    if batch:
        _insert_batch(session, batch)

    session.commit()

    log.info("seed_travel_times_complete", **counts)
    return counts


def _insert_batch(session: Session, batch: list[dict[str, object]]) -> None:
    """Insert a batch of travel time records (no upsert needed — table was cleared)."""
    session.execute(
        text("""
            INSERT INTO travel_times
                (tenant_id, origin_cell_id, destination_id, mode, travel_time_minutes)
            VALUES
                (:tenant_id, :origin_cell_id, :destination_id, :mode, :travel_time_minutes)
        """),
        batch,
    )
