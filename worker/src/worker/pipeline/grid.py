"""Grid generation: create 250 m cells over a tenant's boundary.

The grid is generated in a projected CRS (EPSG:25830 – ETRS89 / UTM 30N)
for metric accuracy, then stored in WGS84 (EPSG:4326).
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# EPSG:25830 – ETRS89 / UTM zone 30N (standard projected CRS for Bizkaia)
PROJECTED_SRID = 25830
STORAGE_SRID = 4326


def build_grid(
    session: Session,
    tenant_id: str,
    cell_size_m: int = 250,
) -> int:
    """Generate a grid of square cells over the tenant's boundary.

    Algorithm:
      1. Read boundary, transform to projected CRS (metric).
      2. Snap bounding box to cell_size grid.
      3. Generate candidate cells via generate_series.
      4. Keep only cells that intersect the boundary.
      5. Transform back to storage CRS and insert.

    Idempotent: deletes existing cells for the tenant before inserting.

    Returns the number of cells created.
    """
    log = logger.bind(tenant_id=tenant_id, cell_size_m=cell_size_m)
    log.info("grid_build_start")

    # Check boundary exists
    boundary_exists = session.execute(
        text("SELECT EXISTS(SELECT 1 FROM boundaries WHERE tenant_id = :tid)"),
        {"tid": tenant_id},
    ).scalar()

    if not boundary_exists:
        raise ValueError(f"No boundary found for tenant {tenant_id}")

    # Delete existing grid cells (cascades to travel_times, scores)
    deleted = session.execute(
        text("DELETE FROM grid_cells WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    ).rowcount
    if deleted:
        log.info("grid_old_cells_deleted", count=deleted)

    # Generate grid via PostGIS
    insert_sql = text("""
        INSERT INTO grid_cells (tenant_id, cell_code, geom, centroid)
        WITH boundary_proj AS (
            SELECT ST_Transform(geom, :proj_srid) AS geom
            FROM boundaries
            WHERE tenant_id = :tid
            LIMIT 1
        ),
        bbox AS (
            SELECT
                (floor(ST_XMin(geom) / :cs) * :cs)::bigint AS xmin,
                (floor(ST_YMin(geom) / :cs) * :cs)::bigint AS ymin,
                (ceil(ST_XMax(geom)  / :cs) * :cs)::bigint AS xmax,
                (ceil(ST_YMax(geom)  / :cs) * :cs)::bigint AS ymax
            FROM boundary_proj
        ),
        grid_raw AS (
            SELECT
                x, y,
                ST_MakeEnvelope(x, y, x + :cs, y + :cs, :proj_srid) AS geom
            FROM bbox,
                generate_series(xmin, xmax - :cs, CAST(:cs_step AS bigint)) AS x,
                generate_series(ymin, ymax - :cs, CAST(:cs_step AS bigint)) AS y
        ),
        grid_clipped AS (
            SELECT g.x, g.y, g.geom
            FROM grid_raw g, boundary_proj b
            WHERE ST_Intersects(g.geom, b.geom)
        )
        SELECT
            :tid,
            'E' || x || '_N' || y,
            ST_Transform(geom, :store_srid),
            ST_Transform(ST_Centroid(geom), :store_srid)
        FROM grid_clipped
    """)

    result = session.execute(insert_sql, {
        "tid": tenant_id,
        "cs": cell_size_m,
        "cs_step": cell_size_m,
        "proj_srid": PROJECTED_SRID,
        "store_srid": STORAGE_SRID,
    })

    cell_count = result.rowcount
    session.commit()

    log.info("grid_build_complete", cells_created=cell_count)
    return cell_count
