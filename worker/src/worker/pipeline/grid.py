"""Grid generation: create 250 m cells over a tenant's boundary.

Uses GeoPandas + Shapely instead of PostGIS.  The grid is generated in
EPSG:25830 (ETRS89 / UTM 30N) for metric accuracy, then stored in
WGS84 (EPSG:4326) as GeoParquet.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import structlog
from shapely.geometry import box

logger = structlog.get_logger()

PROJECTED_CRS = "EPSG:25830"
STORAGE_CRS = "EPSG:4326"


def build_grid(
    tenant_id: str,
    serving_dir: str | Path,
    cell_size_m: int = 250,
) -> int:
    """Generate a grid of square cells over the tenant's boundary.

    Reads ``boundaries.parquet`` from *serving_dir*, generates the grid
    in projected CRS, filters to cells intersecting the boundary, and
    writes ``grid_cells.parquet`` back to *serving_dir*.

    Returns the number of cells created.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, cell_size_m=cell_size_m)
    log.info("grid_build_start")

    # Read boundary
    boundaries_path = serving / "boundaries.parquet"
    if not boundaries_path.exists():
        raise FileNotFoundError(
            f"No boundaries.parquet found in {serving}. "
            "Run import-geoeuskadi first."
        )

    boundaries = gpd.read_parquet(boundaries_path)
    tenant_boundary = boundaries[boundaries["tenant_id"] == tenant_id]
    if tenant_boundary.empty:
        raise ValueError(f"No boundary found for tenant {tenant_id}")

    # Project to UTM for metric grid generation
    boundary_proj = tenant_boundary.to_crs(PROJECTED_CRS)
    boundary_union = boundary_proj.unary_union
    minx, miny, maxx, maxy = boundary_union.bounds

    # Snap to grid
    x0 = int(np.floor(minx / cell_size_m)) * cell_size_m
    y0 = int(np.floor(miny / cell_size_m)) * cell_size_m
    x1 = int(np.ceil(maxx / cell_size_m)) * cell_size_m
    y1 = int(np.ceil(maxy / cell_size_m)) * cell_size_m

    # Generate candidate cells
    xs = np.arange(x0, x1, cell_size_m)
    ys = np.arange(y0, y1, cell_size_m)
    log.info("grid_candidates", x_count=len(xs), y_count=len(ys))

    cells = []
    for x in xs:
        for y in ys:
            cell = box(x, y, x + cell_size_m, y + cell_size_m)
            if cell.intersects(boundary_union):
                cells.append({
                    "cell_code": f"E{int(x)}_N{int(y)}",
                    "geometry": cell,
                })

    grid = gpd.GeoDataFrame(cells, crs=PROJECTED_CRS)
    log.info("grid_clipped", cells=len(grid))

    # Transform to WGS84 for storage
    grid = grid.to_crs(STORAGE_CRS)

    # Add metadata columns
    grid = grid.reset_index(drop=True)
    grid["id"] = grid.index + 1
    grid["tenant_id"] = tenant_id
    grid["population"] = 0.0
    grid["muni_code"] = None

    # Rename geometry to 'geom' for consistency with backend schema
    grid = grid.rename_geometry("geom")

    # Write GeoParquet
    out_path = serving / "grid_cells.parquet"
    grid.to_parquet(out_path)

    log.info("grid_build_complete", cells_created=len(grid), path=str(out_path))
    return len(grid)
