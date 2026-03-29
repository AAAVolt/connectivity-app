"""Export grid-cell origins and destinations as CSV for R5R routing.

R5R's travel_time_matrix() expects origins and destinations as
data.frames with columns: id, lon, lat.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()


def export_r5r_inputs(
    session: Session,
    tenant_id: str,
    output_dir: Path,
) -> dict[str, int]:
    """Write origins.csv and destinations.csv for R5R.

    origins.csv   – grid-cell centroids (id, lon, lat)
    destinations.csv – destination points (id, lon, lat)

    Returns dict with row counts.
    """
    log = logger.bind(tenant_id=tenant_id, output_dir=str(output_dir))
    log.info("export_r5r_start")

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Origins: grid cell centroids ──
    origins = session.execute(
        text("""
            SELECT id, ST_X(centroid) AS lon, ST_Y(centroid) AS lat
            FROM grid_cells
            WHERE tenant_id = :tid
            ORDER BY id
        """),
        {"tid": tenant_id},
    ).fetchall()

    if not origins:
        raise ValueError("No grid cells found — run build-grid first")

    origins_path = output_dir / "origins.csv"
    with open(origins_path, "w") as f:
        f.write("id,lon,lat\n")
        for row in origins:
            f.write(f"{row.id},{row.lon:.8f},{row.lat:.8f}\n")

    # ── Destinations ──
    destinations = session.execute(
        text("""
            SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat
            FROM destinations
            WHERE tenant_id = :tid
            ORDER BY id
        """),
        {"tid": tenant_id},
    ).fetchall()

    if not destinations:
        raise ValueError("No destinations found — run import-geoeuskadi first")

    destinations_path = output_dir / "destinations.csv"
    with open(destinations_path, "w") as f:
        f.write("id,lon,lat\n")
        for row in destinations:
            f.write(f"{row.id},{row.lon:.8f},{row.lat:.8f}\n")

    stats = {
        "origins": len(origins),
        "destinations": len(destinations),
    }
    log.info("export_r5r_complete", **stats)
    return stats
