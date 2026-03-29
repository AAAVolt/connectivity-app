"""Generate synthetic travel times using PostGIS spatial operations.

Much faster than the Python-loop approach in seed_demo.py because:
  - ST_DWithin uses the spatial index to skip distant pairs
  - The entire computation runs server-side in PostgreSQL
  - Only reachable pairs are ever materialised
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# Mode parameters: (speed_kmh, wait_minutes, max_distance_metres)
MODES = {
    "WALK": (3.6, 0.0, 3600),       # 3.6 km/h, no wait, 3.6 km max
    "TRANSIT": (15.0, 5.0, 13750),   # 15 km/h, 5 min wait, 13.75 km max
}

MAX_TRAVEL_TIME = 60.0


def generate_travel_times_sql(
    session: Session,
    tenant_id: str,
) -> dict[str, int]:
    """Generate distance-based travel times using PostGIS ST_Distance.

    For each (cell, destination, mode) within reach, computes:
        travel_time = distance_km / speed_kmh * 60 + wait_minutes

    Uses ST_DWithin on geography type to leverage the spatial index.
    Runs entirely server-side — no Python loops.

    Returns dict with row counts per mode.
    """
    log = logger.bind(tenant_id=tenant_id)
    log.info("sql_travel_times_start")

    # Clear existing
    session.execute(
        text("DELETE FROM travel_times WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )

    counts: dict[str, int] = {}

    for mode, (speed_kmh, wait_min, max_dist_m) in MODES.items():
        log.info("sql_travel_times_mode_start", mode=mode, max_dist_m=max_dist_m)

        result = session.execute(
            text("""
                INSERT INTO travel_times
                    (tenant_id, origin_cell_id, destination_id, mode, travel_time_minutes)
                SELECT
                    gc.tenant_id,
                    gc.id,
                    d.id,
                    :mode,
                    LEAST(
                        ST_Distance(
                            ST_Transform(gc.centroid, 25830),
                            ST_Transform(d.geom, 25830)
                        ) / 1000.0 / :speed * 60.0 + :wait,
                        :max_tt
                    )
                FROM grid_cells gc
                JOIN destinations d
                    ON d.tenant_id = gc.tenant_id
                    AND ST_DWithin(
                        gc.centroid::geography,
                        d.geom::geography,
                        :max_dist
                    )
                WHERE gc.tenant_id = :tid
                  AND ST_Distance(
                        ST_Transform(gc.centroid, 25830),
                        ST_Transform(d.geom, 25830)
                      ) / 1000.0 / :speed * 60.0 + :wait <= :max_tt
            """),
            {
                "tid": tenant_id,
                "mode": mode,
                "speed": speed_kmh,
                "wait": wait_min,
                "max_dist": max_dist_m,
                "max_tt": MAX_TRAVEL_TIME,
            },
        )

        counts[mode] = result.rowcount
        log.info("sql_travel_times_mode_complete", mode=mode, rows=result.rowcount)

    session.commit()
    log.info("sql_travel_times_complete", **counts)
    return counts
