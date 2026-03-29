"""Population disaggregation: areal weighting from source polygons to grid cells.

Distributes population from source polygons (e.g. núcleos, census tracts) to
100 m grid cells proportionally by intersection area.
"""

from __future__ import annotations

import structlog
from shapely.geometry import Polygon as ShapelyPolygon
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# Projected CRS for area calculations (metres)
PROJECTED_SRID = 25830


def areal_weight_pure(
    sources: list[tuple[ShapelyPolygon, float]],
    cells: list[tuple[int, ShapelyPolygon]],
) -> dict[int, float]:
    """Allocate population from source polygons to grid cells by area proportion.

    Pure function (no DB dependency) for unit testing.

    For each cell, sums contributions from all overlapping sources:
        contribution = source_pop * (intersection_area / source_area)

    Args:
        sources: List of (geometry, population) for each source polygon.
        cells: List of (cell_id, geometry) for each grid cell.

    Returns:
        Mapping of cell_id to allocated population.
    """
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
            proportion = isect.area / src_area
            total_pop += src_pop * proportion
        result[cell_id] = total_pop

    return result


def disaggregate_population(
    session: Session,
    tenant_id: str,
) -> dict[str, float]:
    """Disaggregate population from source polygons to grid cells.

    Uses PostGIS for all spatial operations (performant on large grids).
    Area calculations use projected CRS (EPSG:25830) for metric accuracy.

    Idempotent: resets all cell populations to 0 before recalculating.

    Returns statistics dict with totals and counts.
    """
    log = logger.bind(tenant_id=tenant_id)
    log.info("population_disaggregation_start")

    # Check prerequisites
    cell_count = session.execute(
        text("SELECT COUNT(*) FROM grid_cells WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    ).scalar()
    if not cell_count:
        raise ValueError(
            f"No grid cells found for tenant {tenant_id}. Run build-grid first."
        )

    source_count = session.execute(
        text("SELECT COUNT(*) FROM population_sources WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    ).scalar()
    if not source_count:
        raise ValueError(
            f"No population sources found for tenant {tenant_id}."
        )

    # Total source population (for validation)
    total_source_pop = session.execute(
        text(
            "SELECT COALESCE(SUM(population), 0) "
            "FROM population_sources WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    ).scalar()

    # Reset all populations to zero
    session.execute(
        text("UPDATE grid_cells SET population = 0 WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )

    # Areal weighting via PostGIS:
    #   For each (grid_cell, population_source) intersection,
    #   allocated = source_pop * (intersection_area / source_area)
    update_sql = text("""
        UPDATE grid_cells gc
        SET population = agg.pop
        FROM (
            SELECT
                gc2.id AS cell_id,
                SUM(
                    ps.population
                    * ST_Area(
                        ST_Transform(ST_Intersection(gc2.geom, ps.geom), :proj_srid)
                      )
                    / NULLIF(
                        ST_Area(ST_Transform(ps.geom, :proj_srid)),
                        0
                      )
                ) AS pop
            FROM grid_cells gc2
            JOIN population_sources ps
                ON ST_Intersects(gc2.geom, ps.geom)
               AND gc2.tenant_id = ps.tenant_id
            WHERE gc2.tenant_id = :tid
            GROUP BY gc2.id
        ) agg
        WHERE gc.id = agg.cell_id
    """)

    result = session.execute(update_sql, {
        "tid": tenant_id,
        "proj_srid": PROJECTED_SRID,
    })
    cells_updated = result.rowcount

    # Compute summary statistics
    stats_row = session.execute(
        text("""
            SELECT
                COALESCE(SUM(population), 0)                    AS total_pop,
                COUNT(*) FILTER (WHERE population > 0)          AS cells_with_pop,
                COUNT(*)                                        AS total_cells
            FROM grid_cells
            WHERE tenant_id = :tid
        """),
        {"tid": tenant_id},
    ).one()

    session.commit()

    stats = {
        "source_population": float(total_source_pop),
        "allocated_population": float(stats_row.total_pop),
        "cells_with_population": int(stats_row.cells_with_pop),
        "total_cells": int(stats_row.total_cells),
        "cells_updated": cells_updated,
    }

    log.info("population_disaggregation_complete", **stats)
    return stats
