"""Population disaggregation: areal weighting from source polygons to grid cells.

Distributes population from source polygons (e.g. núcleos, census tracts) to
250 m grid cells proportionally by intersection area.
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


def dasymetric_weight_pure(
    sources: list[tuple[ShapelyPolygon, float]],
    cells: list[tuple[int, ShapelyPolygon]],
    mask: ShapelyPolygon,
) -> dict[int, float]:
    """Allocate population with dasymetric masking (pure function).

    Mirrors the PostGIS dasymetric SQL: population from each source is
    redistributed only into the intersection of the source with *mask*.
    Cells outside the mask receive zero.

    For each (cell, source) pair:
        masked_src   = source ∩ mask
        contribution = source_pop × area(cell ∩ masked_src) / area(masked_src)

    Args:
        sources: List of (geometry, population) for each source polygon.
        cells: List of (cell_id, geometry) for each grid cell.
        mask: Union of all núcleo polygons (non-diseminado).

    Returns:
        Mapping of cell_id to allocated population.
    """
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
            proportion = isect.area / masked_area
            total_pop += src_pop * proportion
        result[cell_id] = total_pop

    return result


def disaggregate_population(
    session: Session,
    tenant_id: str,
    *,
    use_nucleos: bool = True,
) -> dict[str, float]:
    """Disaggregate population from source polygons to grid cells.

    Uses PostGIS for all spatial operations (performant on large grids).
    Area calculations use projected CRS (EPSG:25830) for metric accuracy.

    When *use_nucleos* is True and the ``nucleos`` table has data for
    this tenant, only grid cells that intersect a **núcleo** polygon
    (``nucleo_num != '99'``) receive population (dasymetric masking).
    Population within each source is redistributed proportionally to
    the area of each cell's intersection with **both** the source and
    a núcleo.  Cells in *diseminado* (dispersed rural) areas get 0.

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

    # Decide whether to apply dasymetric masking via nucleos
    nucleo_count = 0
    if use_nucleos:
        nucleo_count = session.execute(
            text(
                "SELECT COUNT(*) FROM nucleos "
                "WHERE tenant_id = :tid AND nucleo_num != '99'"
            ),
            {"tid": tenant_id},
        ).scalar() or 0

    has_nucleos = nucleo_count > 0
    if use_nucleos and not has_nucleos:
        log.info("population_no_nucleos_found_falling_back_to_areal")

    if has_nucleos:
        log.info("population_dasymetric_mode", nucleo_count=nucleo_count)
        # Build a single unified mask from all núcleo polygons (ST_Union)
        # so that overlapping núcleos don't double-count.
        #
        # For each source we compute:
        #   denominator = area(source ∩ nucleo_mask)    -- total "settled" area
        #   numerator   = area(cell ∩ source ∩ nucleo_mask) per cell
        #   cell_pop    = source_pop × numerator / denominator
        #
        # This guarantees that the sum of allocations from each source
        # equals source_pop (conservation, modulo boundary clipping).
        update_sql = text("""
            WITH nucleo_mask AS (
                SELECT ST_Union(ST_MakeValid(geom)) AS geom
                FROM nucleos
                WHERE tenant_id = :tid AND nucleo_num != '99'
            ),
            masked_sources AS (
                SELECT
                    ps.id AS source_id,
                    ps.population,
                    ST_Intersection(ST_MakeValid(ps.geom), nm.geom) AS masked_geom,
                    ST_Area(ST_Transform(
                        ST_Intersection(ST_MakeValid(ps.geom), nm.geom),
                        :proj_srid
                    )) AS masked_area
                FROM population_sources ps, nucleo_mask nm
                WHERE ps.tenant_id = :tid
                  AND ST_Intersects(ps.geom, nm.geom)
            )
            UPDATE grid_cells gc
            SET population = agg.pop
            FROM (
                SELECT
                    gc2.id AS cell_id,
                    SUM(
                        ms.population
                        * ST_Area(ST_Transform(
                            ST_Intersection(gc2.geom, ms.masked_geom),
                            :proj_srid
                          ))
                        / NULLIF(ms.masked_area, 0)
                    ) AS pop
                FROM grid_cells gc2
                JOIN masked_sources ms
                    ON ST_Intersects(gc2.geom, ms.masked_geom)
                WHERE gc2.tenant_id = :tid
                GROUP BY gc2.id
            ) agg
            WHERE gc.id = agg.cell_id
        """)
    else:
        # Plain areal weighting (original behaviour)
        update_sql = text("""
            UPDATE grid_cells gc
            SET population = agg.pop
            FROM (
                SELECT
                    gc2.id AS cell_id,
                    SUM(
                        ps.population
                        * ST_Area(
                            ST_Transform(
                                ST_Intersection(gc2.geom, ST_MakeValid(ps.geom)),
                                :proj_srid
                            )
                          )
                        / NULLIF(
                            ST_Area(ST_Transform(ST_MakeValid(ps.geom), :proj_srid)),
                            0
                          )
                    ) AS pop
                FROM grid_cells gc2
                JOIN population_sources ps
                    ON ST_Intersects(gc2.geom, ST_MakeValid(ps.geom))
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

    allocated = float(stats_row.total_pop)
    source = float(total_source_pop)

    stats: dict[str, float] = {
        "source_population": source,
        "allocated_population": allocated,
        "cells_with_population": int(stats_row.cells_with_pop),
        "total_cells": int(stats_row.total_cells),
        "cells_updated": cells_updated,
        "dasymetric": 1.0 if has_nucleos else 0.0,
    }

    # Warn if totals diverge by more than 5% (dasymetric deliberately
    # discards diseminado population, so expect higher loss)
    if source > 0:
        loss_pct = abs(source - allocated) / source * 100
        stats["loss_pct"] = round(loss_pct, 4)
        threshold = 10.0 if has_nucleos else 0.1
        if loss_pct > threshold:
            log.warning(
                "population_conservation_warning",
                source=source,
                allocated=allocated,
                loss_pct=round(loss_pct, 2),
                mode="dasymetric" if has_nucleos else "areal",
            )

    log.info("population_disaggregation_complete", **stats)
    return stats
