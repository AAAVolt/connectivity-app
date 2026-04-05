"""Export grid-cell origins and destinations as CSV for R5R routing.

R5R's travel_time_matrix() expects origins and destinations as
data.frames with columns: id, lon, lat.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import structlog

logger = structlog.get_logger()


def export_r5r_inputs(
    tenant_id: str,
    serving_dir: str | Path,
    output_dir: Path,
) -> dict[str, int]:
    """Write origins.csv and destinations.csv for R5R.

    Reads grid_cells.parquet and destinations.parquet from serving_dir.
    Returns dict with row counts.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, output_dir=str(output_dir))
    log.info("export_r5r_start")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Origins: grid cell centroids
    grid = gpd.read_parquet(serving / "grid_cells.parquet")
    grid_tenant = grid[grid["tenant_id"] == tenant_id]
    if grid_tenant.empty:
        raise ValueError("No grid cells found - run build-grid first")

    centroids = grid_tenant.geometry.centroid
    origins_path = output_dir / "origins.csv"
    with open(origins_path, "w") as f:
        f.write("id,lon,lat\n")
        for idx, row in grid_tenant.iterrows():
            centroid = centroids.loc[idx]
            f.write(f"{row['id']},{centroid.x:.8f},{centroid.y:.8f}\n")

    # Destinations
    dests = gpd.read_parquet(serving / "destinations.parquet")
    dests_tenant = dests[dests["tenant_id"] == tenant_id]
    if dests_tenant.empty:
        raise ValueError("No destinations found - run import-geoeuskadi first")

    destinations_path = output_dir / "destinations.csv"
    with open(destinations_path, "w") as f:
        f.write("id,lon,lat\n")
        for _, row in dests_tenant.iterrows():
            pt = row.geometry
            f.write(f"{row['id']},{pt.x:.8f},{pt.y:.8f}\n")

    stats = {
        "origins": len(grid_tenant),
        "destinations": len(dests_tenant),
    }
    log.info("export_r5r_complete", **stats)
    return stats
