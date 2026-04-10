"""Population disaggregation: areal weighting from source polygons to grid cells.

Uses GeoPandas overlay instead of PostGIS.  All area calculations run
in EPSG:25830 (projected CRS) for metric accuracy.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import structlog

logger = structlog.get_logger()

PROJECTED_CRS = "EPSG:25830"


def areal_weight_pure(
    sources: list[tuple[object, float]],
    cells: list[tuple[int, object]],
) -> dict[int, float]:
    """Allocate population by area proportion (pure function for testing)."""
    from shapely.geometry import Polygon as ShapelyPolygon  # noqa: F811

    result: dict[int, float] = {}
    for cell_id, cell_geom in cells:
        total_pop = 0.0
        for src_geom, src_pop in sources:
            if not cell_geom.intersects(src_geom):
                continue
            src_area = src_geom.area
            if src_area <= 0:
                continue
            isect = cell_geom.intersection(src_geom)
            total_pop += src_pop * (isect.area / src_area)
        result[cell_id] = total_pop
    return result


def dasymetric_weight_pure(
    sources: list[tuple[object, float]],
    cells: list[tuple[int, object]],
    mask: object,
) -> dict[int, float]:
    """Allocate population with dasymetric masking (pure function)."""
    result: dict[int, float] = {}
    for cell_id, cell_geom in cells:
        total_pop = 0.0
        for src_geom, src_pop in sources:
            masked_src = src_geom.intersection(mask)
            if masked_src.is_empty:
                continue
            masked_area = masked_src.area
            if masked_area <= 0:
                continue
            if not cell_geom.intersects(masked_src):
                continue
            isect = cell_geom.intersection(masked_src)
            total_pop += src_pop * (isect.area / masked_area)
        result[cell_id] = total_pop
    return result


def disaggregate_population(
    tenant_id: str,
    serving_dir: str | Path,
    *,
    use_nucleos: bool = True,
) -> dict[str, float]:
    """Disaggregate population from source polygons to grid cells.

    Uses GeoPandas overlay for all spatial operations.  Area calculations
    use EPSG:25830 for metric accuracy.

    Reads ``grid_cells.parquet``, ``population_sources.parquet``, and
    optionally ``nucleos.parquet``.  Updates the ``population`` column
    in ``grid_cells.parquet``.

    Returns statistics dict with totals and counts.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id)
    log.info("population_disaggregation_start")

    # Read inputs
    grid_path = serving / "grid_cells.parquet"
    pop_path = serving / "population_sources.parquet"

    grid = gpd.read_parquet(grid_path)
    grid_tenant = grid[grid["tenant_id"] == tenant_id].copy()
    if grid_tenant.empty:
        raise ValueError(f"No grid cells for tenant {tenant_id}. Run build-grid first.")

    pop_sources = gpd.read_parquet(pop_path)
    pop_tenant = pop_sources[pop_sources["tenant_id"] == tenant_id].copy()
    if pop_tenant.empty:
        raise ValueError(f"No population sources for tenant {tenant_id}.")

    total_source_pop = float(pop_tenant["population"].sum())

    # Project to metric CRS for area calculations
    grid_proj = grid_tenant.to_crs(PROJECTED_CRS)
    pop_proj = pop_tenant.to_crs(PROJECTED_CRS)

    # Check for nucleos (dasymetric masking)
    nucleos_path = serving / "nucleos.parquet"
    has_nucleos = False
    if use_nucleos and nucleos_path.exists():
        nucleos = gpd.read_parquet(nucleos_path)
        nucleos_tenant = nucleos[
            (nucleos["tenant_id"] == tenant_id) & (nucleos["nucleo_num"] != "99")
        ]
        if not nucleos_tenant.empty:
            has_nucleos = True
            nucleos_proj = nucleos_tenant.to_crs(PROJECTED_CRS)
            nucleo_mask = nucleos_proj.unary_union
            log.info("population_dasymetric_mode", nucleo_count=len(nucleos_proj))

    if has_nucleos:
        # Dasymetric: clip sources to nucleo mask
        # For each source, masked_geom = source ∩ nucleo_mask
        pop_proj = pop_proj.copy()
        pop_proj["masked_geom"] = pop_proj.geometry.intersection(nucleo_mask)
        pop_proj["masked_area"] = pop_proj["masked_geom"].area
        # Filter out sources with no overlap
        pop_proj = pop_proj[pop_proj["masked_area"] > 0].copy()
        pop_proj = pop_proj.set_geometry("masked_geom")
    else:
        pop_proj["masked_area"] = pop_proj.geometry.area
        log.info("population_areal_weighting_mode")

    # Overlay grid with population sources
    # Using spatial join + intersection area calculation
    grid_proj = grid_proj.reset_index(drop=True)
    grid_proj["grid_idx"] = grid_proj.index

    # Spatial overlay to find intersecting pairs
    grid_geom_col = grid_proj.geometry.name
    pop_geom_col = pop_proj.geometry.name
    overlay = gpd.overlay(
        grid_proj[["grid_idx", "id", grid_geom_col]],
        pop_proj[["population", "masked_area", pop_geom_col]],
        how="intersection",
        keep_geom_type=False,
    )

    if overlay.empty:
        log.warning("population_no_overlap")
        # Reset populations to 0
        grid.loc[grid["tenant_id"] == tenant_id, "population"] = 0.0
        grid.to_parquet(grid_path)
        return {
            "source_population": total_source_pop,
            "allocated_population": 0.0,
            "cells_with_population": 0,
            "total_cells": len(grid_tenant),
            "dasymetric": 1.0 if has_nucleos else 0.0,
        }

    # Calculate area-proportional population
    overlay["overlap_area"] = overlay.geometry.area
    overlay["pop_share"] = (
        overlay["population"] * overlay["overlap_area"] / overlay["masked_area"]
    )

    # Aggregate per grid cell
    cell_pops = overlay.groupby("id")["pop_share"].sum()

    # Update grid populations
    grid.loc[grid["tenant_id"] == tenant_id, "population"] = 0.0
    mask = grid["id"].isin(cell_pops.index) & (grid["tenant_id"] == tenant_id)
    grid.loc[mask, "population"] = grid.loc[mask, "id"].map(cell_pops).fillna(0.0)

    # Write updated grid
    grid.to_parquet(grid_path)

    allocated = float(grid.loc[grid["tenant_id"] == tenant_id, "population"].sum())
    cells_with_pop = int((grid.loc[grid["tenant_id"] == tenant_id, "population"] > 0).sum())

    stats: dict[str, float] = {
        "source_population": total_source_pop,
        "allocated_population": allocated,
        "cells_with_population": cells_with_pop,
        "total_cells": len(grid_tenant),
        "dasymetric": 1.0 if has_nucleos else 0.0,
    }

    if total_source_pop > 0:
        loss_pct = abs(total_source_pop - allocated) / total_source_pop * 100
        stats["loss_pct"] = round(loss_pct, 4)

    log.info("population_disaggregation_complete", **stats)
    return stats
