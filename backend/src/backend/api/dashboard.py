"""Dashboard analytics endpoints.

Pre-aggregated statistics for the connectivity dashboard:
summary KPIs, score distributions, purpose breakdowns,
municipality/comarca rankings, and service coverage thresholds.
"""

from __future__ import annotations

import logging
from typing import Any

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.api.cells import DEFAULT_DEPARTURE_TIME, _validate_departure_time
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import DuckDBSession, get_db

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DashboardSummary(BaseModel):
    total_cells: int
    populated_cells: int
    total_population: float
    cells_with_scores: int
    avg_score: float | None
    weighted_avg_score: float | None
    median_score: float | None
    destination_count: int
    transit_stop_count: int
    transit_route_count: int
    municipality_count: int
    comarca_count: int


class ScoreDistributionBucket(BaseModel):
    range_label: str
    range_min: float
    range_max: float
    cell_count: int
    population: float


class PurposeBreakdown(BaseModel):
    mode: str
    purpose: str
    purpose_label: str
    avg_score: float | None
    weighted_avg_score: float | None
    avg_travel_time: float | None
    cell_count: int


class AreaRanking(BaseModel):
    name: str
    code: str
    cell_count: int
    population: float
    avg_score: float | None
    weighted_avg_score: float | None


class ServiceCoverage(BaseModel):
    purpose: str
    purpose_label: str
    mode: str
    total_cells: int
    total_population: float
    pop_15min: float
    pop_30min: float
    pop_45min: float
    pop_60min: float
    pct_pop_15min: float
    pct_pop_30min: float
    pct_pop_45min: float
    pct_pop_60min: float
    avg_travel_time: float | None
    median_travel_time: float | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    departure_time: str = Query(
        DEFAULT_DEPARTURE_TIME,
        description="Departure time slot (HH:MM)",
    ),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> DashboardSummary:
    """High-level KPIs for the dashboard header."""
    dep_time = _validate_departure_time(departure_time)

    result = db.execute(
        """
        SELECT
            COUNT(*)                                        AS total_cells,
            COUNT(*) FILTER (WHERE gc.population > 0)       AS populated_cells,
            COALESCE(SUM(gc.population), 0)                 AS total_population,
            COUNT(cs.id)                                    AS cells_with_scores,
            AVG(cs.combined_score_normalized)                AS avg_score,
            CASE
                WHEN SUM(gc.population) > 0 THEN
                    SUM(gc.population * COALESCE(cs.combined_score_normalized, 0))
                    / SUM(gc.population)
                ELSE AVG(cs.combined_score_normalized)
            END                                             AS weighted_avg_score,
            quantile_cont(cs.combined_score_normalized, 0.5)
                                                            AS median_score
        FROM grid_cells gc
        LEFT JOIN combined_scores cs
            ON cs.cell_id = gc.id
            AND cs.tenant_id = gc.tenant_id
            AND cs.departure_time = $dep_time
        WHERE gc.tenant_id = $tid
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time},
    )
    main = result.one()

    # Count auxiliary tables — some may not exist in demo/minimal setups
    def _safe_count(table: str, where: str = "") -> int:
        try:
            q = f"SELECT COUNT(*) AS c FROM {table}"
            params: dict[str, Any] = {}
            if where:
                q += f" WHERE {where}"
                params["tid"] = tenant.tenant_id
            return db.execute(q, params).one().c
        except (duckdb.CatalogException, duckdb.BinderException):
            # Table doesn't exist in this dataset — expected in minimal setups
            return 0
        except Exception:
            _logger.warning("_safe_count failed for table=%s", table, exc_info=True)
            return 0

    class _Counts:
        dest_count = _safe_count("destinations", "tenant_id = $tid")
        stop_count = _safe_count("gtfs_stops")
        route_count = _safe_count("gtfs_routes")
        muni_count = _safe_count("municipalities", "tenant_id = $tid")
        comarca_count = _safe_count("comarcas", "tenant_id = $tid")

    c = _Counts()

    return DashboardSummary(
        total_cells=main.total_cells,
        populated_cells=main.populated_cells,
        total_population=float(main.total_population),
        cells_with_scores=main.cells_with_scores,
        avg_score=_f(main.avg_score),
        weighted_avg_score=_f(main.weighted_avg_score),
        median_score=_f(main.median_score),
        destination_count=c.dest_count,
        transit_stop_count=c.stop_count,
        transit_route_count=c.route_count,
        municipality_count=c.muni_count,
        comarca_count=c.comarca_count,
    )


@router.get("/score-distribution", response_model=list[ScoreDistributionBucket])
def get_score_distribution(
    departure_time: str = Query(DEFAULT_DEPARTURE_TIME),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[ScoreDistributionBucket]:
    """Score distribution histogram (10 buckets, 0-100)."""
    dep_time = _validate_departure_time(departure_time)

    result = db.execute(
        """
        WITH scored AS (
            SELECT gc.population, cs.combined_score_normalized AS score
            FROM grid_cells gc
            JOIN combined_scores cs
                ON cs.cell_id = gc.id
                AND cs.tenant_id = gc.tenant_id
                AND cs.departure_time = $dep_time
            WHERE gc.tenant_id = $tid
                AND cs.combined_score_normalized IS NOT NULL
        ),
        buckets AS (
            SELECT
                LEAST(GREATEST(CAST(floor(score / 10) + 1 AS INTEGER), 1), 10) AS bucket,
                COUNT(*)           AS cell_count,
                COALESCE(SUM(population), 0) AS population
            FROM scored
            GROUP BY 1
        )
        SELECT bucket, cell_count, population
        FROM buckets
        ORDER BY bucket
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time},
    )

    labels = [
        ("0-10", 0, 10), ("10-20", 10, 20), ("20-30", 20, 30),
        ("30-40", 30, 40), ("40-50", 40, 50), ("50-60", 50, 60),
        ("60-70", 60, 70), ("70-80", 70, 80), ("80-90", 80, 90),
        ("90-100", 90, 100),
    ]

    filled: dict[int, tuple[int, float]] = {}
    for row in result.fetchall():
        filled[row.bucket] = (row.cell_count, float(row.population))

    return [
        ScoreDistributionBucket(
            range_label=label,
            range_min=lo,
            range_max=hi,
            cell_count=filled.get(i + 1, (0, 0.0))[0],
            population=filled.get(i + 1, (0, 0.0))[1],
        )
        for i, (label, lo, hi) in enumerate(labels)
    ]


@router.get("/purpose-breakdown", response_model=list[PurposeBreakdown])
def get_purpose_breakdown(
    departure_time: str = Query(DEFAULT_DEPARTURE_TIME),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[PurposeBreakdown]:
    """Average scores and travel times broken down by mode and purpose."""
    dep_time = _validate_departure_time(departure_time)

    dt_result = db.execute(
        "SELECT code, label FROM destination_types ORDER BY code"
    )
    label_map: dict[str, str] = {
        row.code: row.label for row in dt_result.fetchall()
    }

    result = db.execute(
        """
        SELECT
            cs.mode,
            cs.purpose,
            AVG(cs.score_normalized)  AS avg_score,
            CASE
                WHEN SUM(gc.population) > 0 THEN
                    SUM(gc.population * COALESCE(cs.score_normalized, 0))
                    / SUM(gc.population)
                ELSE AVG(cs.score_normalized)
            END                       AS weighted_avg_score,
            COUNT(*)                  AS cell_count
        FROM connectivity_scores cs
        JOIN grid_cells gc
            ON gc.id = cs.cell_id AND gc.tenant_id = cs.tenant_id
        WHERE cs.tenant_id = $tid
            AND cs.departure_time = $dep_time
        GROUP BY cs.mode, cs.purpose
        ORDER BY cs.mode, cs.purpose
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time},
    )
    scores_map: dict[tuple[str, str], dict] = {}
    for row in result.fetchall():
        scores_map[(row.mode, row.purpose)] = {
            "avg_score": _f(row.avg_score),
            "weighted_avg_score": _f(row.weighted_avg_score),
            "cell_count": row.cell_count,
        }

    tt_result = db.execute(
        """
        SELECT
            mt.mode,
            mt.purpose,
            AVG(mt.min_travel_time_minutes) AS avg_tt
        FROM min_travel_times mt
        WHERE mt.tenant_id = $tid
            AND mt.departure_time = $dep_time
        GROUP BY mt.mode, mt.purpose
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time},
    )
    tt_map: dict[tuple[str, str], float | None] = {}
    for row in tt_result.fetchall():
        tt_map[(row.mode, row.purpose)] = _f(row.avg_tt)

    out: list[PurposeBreakdown] = []
    for (mode, purpose), data in sorted(scores_map.items()):
        out.append(PurposeBreakdown(
            mode=mode,
            purpose=purpose,
            purpose_label=label_map.get(purpose, purpose),
            avg_score=data["avg_score"],
            weighted_avg_score=data["weighted_avg_score"],
            avg_travel_time=tt_map.get((mode, purpose)),
            cell_count=data["cell_count"],
        ))

    return out


@router.get("/municipality-ranking", response_model=list[AreaRanking])
def get_municipality_ranking(
    departure_time: str = Query(DEFAULT_DEPARTURE_TIME),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[AreaRanking]:
    """Municipality-level aggregated connectivity scores (spatial join)."""
    dep_time = _validate_departure_time(departure_time)

    result = db.execute(
        """
        SELECT
            m.name,
            m.muni_code                        AS code,
            COUNT(gc.id)                       AS cell_count,
            COALESCE(SUM(gc.population), 0)    AS population,
            AVG(cs.combined_score_normalized)   AS avg_score,
            CASE
                WHEN SUM(gc.population) > 0 THEN
                    SUM(gc.population * COALESCE(cs.combined_score_normalized, 0))
                    / SUM(gc.population)
                ELSE AVG(cs.combined_score_normalized)
            END                                AS weighted_avg_score
        FROM municipalities m
        JOIN grid_cells gc
            ON gc.tenant_id = m.tenant_id
            AND ST_Intersects(gc.centroid, m.geom)
        LEFT JOIN combined_scores cs
            ON cs.cell_id = gc.id
            AND cs.tenant_id = gc.tenant_id
            AND cs.departure_time = $dep_time
        WHERE m.tenant_id = $tid
        GROUP BY m.name, m.muni_code
        ORDER BY weighted_avg_score DESC NULLS LAST
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time},
    )

    return [
        AreaRanking(
            name=row.name,
            code=row.code,
            cell_count=row.cell_count,
            population=float(row.population),
            avg_score=_f(row.avg_score),
            weighted_avg_score=_f(row.weighted_avg_score),
        )
        for row in result.fetchall()
    ]


@router.get("/comarca-ranking", response_model=list[AreaRanking])
def get_comarca_ranking(
    departure_time: str = Query(DEFAULT_DEPARTURE_TIME),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[AreaRanking]:
    """Comarca-level aggregated connectivity scores (spatial join)."""
    dep_time = _validate_departure_time(departure_time)

    result = db.execute(
        """
        SELECT
            c.name,
            c.comarca_code                     AS code,
            COUNT(gc.id)                       AS cell_count,
            COALESCE(SUM(gc.population), 0)    AS population,
            AVG(cs.combined_score_normalized)   AS avg_score,
            CASE
                WHEN SUM(gc.population) > 0 THEN
                    SUM(gc.population * COALESCE(cs.combined_score_normalized, 0))
                    / SUM(gc.population)
                ELSE AVG(cs.combined_score_normalized)
            END                                AS weighted_avg_score
        FROM comarcas c
        JOIN grid_cells gc
            ON gc.tenant_id = c.tenant_id
            AND ST_Intersects(gc.centroid, c.geom)
        LEFT JOIN combined_scores cs
            ON cs.cell_id = gc.id
            AND cs.tenant_id = gc.tenant_id
            AND cs.departure_time = $dep_time
        WHERE c.tenant_id = $tid
        GROUP BY c.name, c.comarca_code
        ORDER BY weighted_avg_score DESC NULLS LAST
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time},
    )

    return [
        AreaRanking(
            name=row.name,
            code=row.code,
            cell_count=row.cell_count,
            population=float(row.population),
            avg_score=_f(row.avg_score),
            weighted_avg_score=_f(row.weighted_avg_score),
        )
        for row in result.fetchall()
    ]


@router.get("/service-coverage", response_model=list[ServiceCoverage])
def get_service_coverage(
    departure_time: str = Query(DEFAULT_DEPARTURE_TIME),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[ServiceCoverage]:
    """Percentage of population within travel-time thresholds per service."""
    dep_time = _validate_departure_time(departure_time)

    dt_result = db.execute(
        "SELECT code, label FROM destination_types ORDER BY code"
    )
    label_map: dict[str, str] = {
        row.code: row.label for row in dt_result.fetchall()
    }

    result = db.execute(
        """
        SELECT
            mt.purpose,
            mt.mode,
            COUNT(*)                             AS total_cells,
            COALESCE(SUM(gc.population), 0)      AS total_population,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 15), 0)
                                                 AS pop_15min,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 30), 0)
                                                 AS pop_30min,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 45), 0)
                                                 AS pop_45min,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 60), 0)
                                                 AS pop_60min,
            AVG(mt.min_travel_time_minutes)      AS avg_tt,
            quantile_cont(mt.min_travel_time_minutes, 0.5)
                                                 AS median_tt
        FROM min_travel_times mt
        JOIN grid_cells gc
            ON gc.id = mt.cell_id AND gc.tenant_id = mt.tenant_id
        WHERE mt.tenant_id = $tid
            AND mt.departure_time = $dep_time
        GROUP BY mt.purpose, mt.mode
        ORDER BY mt.purpose, mt.mode
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time},
    )

    return [
        ServiceCoverage(
            purpose=row.purpose,
            purpose_label=label_map.get(row.purpose, row.purpose),
            mode=row.mode,
            total_cells=row.total_cells,
            total_population=float(row.total_population),
            pop_15min=float(row.pop_15min),
            pop_30min=float(row.pop_30min),
            pop_45min=float(row.pop_45min),
            pop_60min=float(row.pop_60min),
            pct_pop_15min=_pct(row.pop_15min, row.total_population),
            pct_pop_30min=_pct(row.pop_30min, row.total_population),
            pct_pop_45min=_pct(row.pop_45min, row.total_population),
            pct_pop_60min=_pct(row.pop_60min, row.total_population),
            avg_travel_time=_f(row.avg_tt),
            median_travel_time=_f(row.median_tt),
        )
        for row in result.fetchall()
    ]


class AreaDetail(BaseModel):
    """Full detail for a single comarca or municipality."""
    name: str
    code: str
    cell_count: int
    population: float
    avg_score: float | None
    weighted_avg_score: float | None
    purpose_scores: list[PurposeBreakdown]
    service_coverage: list[ServiceCoverage]


def _area_detail(
    *,
    table: str,
    code_col: str,
    code_value: str,
    dep_time: str,
    tenant: TenantContext,
    db: DuckDBSession,
) -> AreaDetail:
    """Shared logic for comarca / municipality detail endpoints."""
    dt_result = db.execute(
        "SELECT code, label FROM destination_types ORDER BY code"
    )
    label_map: dict[str, str] = {
        row.code: row.label for row in dt_result.fetchall()
    }

    # Summary
    summary = db.execute(
        f"""
        SELECT
            a.name,
            a.{code_col}                           AS code,
            COUNT(gc.id)                           AS cell_count,
            COALESCE(SUM(gc.population), 0)        AS population,
            AVG(cs.combined_score_normalized)       AS avg_score,
            CASE
                WHEN SUM(gc.population) > 0 THEN
                    SUM(gc.population * COALESCE(cs.combined_score_normalized, 0))
                    / SUM(gc.population)
                ELSE AVG(cs.combined_score_normalized)
            END                                    AS weighted_avg_score
        FROM {table} a
        JOIN grid_cells gc
            ON gc.tenant_id = a.tenant_id
            AND ST_Intersects(gc.centroid, a.geom)
        LEFT JOIN combined_scores cs
            ON cs.cell_id = gc.id
            AND cs.tenant_id = gc.tenant_id
            AND cs.departure_time = $dep_time
        WHERE a.tenant_id = $tid AND a.{code_col} = $code
        GROUP BY a.name, a.{code_col}
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time, "code": code_value},
    )
    s = summary.one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Area not found")

    # Purpose breakdown within area
    pb_result = db.execute(
        f"""
        SELECT
            cs.mode,
            cs.purpose,
            AVG(cs.score_normalized)  AS avg_score,
            CASE
                WHEN SUM(gc.population) > 0 THEN
                    SUM(gc.population * COALESCE(cs.score_normalized, 0))
                    / SUM(gc.population)
                ELSE AVG(cs.score_normalized)
            END                       AS weighted_avg_score,
            COUNT(*)                  AS cell_count
        FROM {table} a
        JOIN grid_cells gc
            ON gc.tenant_id = a.tenant_id
            AND ST_Intersects(gc.centroid, a.geom)
        JOIN connectivity_scores cs
            ON cs.cell_id = gc.id
            AND cs.tenant_id = gc.tenant_id
            AND cs.departure_time = $dep_time
        WHERE a.tenant_id = $tid AND a.{code_col} = $code
        GROUP BY cs.mode, cs.purpose
        ORDER BY cs.mode, cs.purpose
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time, "code": code_value},
    )

    purpose_scores: list[PurposeBreakdown] = []
    for row in pb_result.fetchall():
        purpose_scores.append(PurposeBreakdown(
            mode=row.mode,
            purpose=row.purpose,
            purpose_label=label_map.get(row.purpose, row.purpose),
            avg_score=_f(row.avg_score),
            weighted_avg_score=_f(row.weighted_avg_score),
            avg_travel_time=None,
            cell_count=row.cell_count,
        ))

    # Travel times within area
    tt_result = db.execute(
        f"""
        SELECT
            mt.mode,
            mt.purpose,
            AVG(mt.min_travel_time_minutes) AS avg_tt
        FROM {table} a
        JOIN grid_cells gc
            ON gc.tenant_id = a.tenant_id
            AND ST_Intersects(gc.centroid, a.geom)
        JOIN min_travel_times mt
            ON mt.cell_id = gc.id
            AND mt.tenant_id = gc.tenant_id
            AND mt.departure_time = $dep_time
        WHERE a.tenant_id = $tid AND a.{code_col} = $code
        GROUP BY mt.mode, mt.purpose
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time, "code": code_value},
    )
    tt_map: dict[tuple[str, str], float | None] = {}
    for row in tt_result.fetchall():
        tt_map[(row.mode, row.purpose)] = _f(row.avg_tt)

    for ps in purpose_scores:
        ps.avg_travel_time = tt_map.get((ps.mode, ps.purpose))

    # Service coverage within area
    cov_result = db.execute(
        f"""
        SELECT
            mt.purpose,
            mt.mode,
            COUNT(*)                             AS total_cells,
            COALESCE(SUM(gc.population), 0)      AS total_population,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 15), 0)
                                                 AS pop_15min,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 30), 0)
                                                 AS pop_30min,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 45), 0)
                                                 AS pop_45min,
            COALESCE(SUM(gc.population)
                FILTER (WHERE mt.min_travel_time_minutes <= 60), 0)
                                                 AS pop_60min,
            AVG(mt.min_travel_time_minutes)      AS avg_tt,
            quantile_cont(mt.min_travel_time_minutes, 0.5)
                                                 AS median_tt
        FROM {table} a
        JOIN grid_cells gc
            ON gc.tenant_id = a.tenant_id
            AND ST_Intersects(gc.centroid, a.geom)
        JOIN min_travel_times mt
            ON mt.cell_id = gc.id
            AND mt.tenant_id = gc.tenant_id
            AND mt.departure_time = $dep_time
        WHERE a.tenant_id = $tid AND a.{code_col} = $code
        GROUP BY mt.purpose, mt.mode
        ORDER BY mt.purpose, mt.mode
        """,
        {"tid": tenant.tenant_id, "dep_time": dep_time, "code": code_value},
    )

    service_coverage = [
        ServiceCoverage(
            purpose=row.purpose,
            purpose_label=label_map.get(row.purpose, row.purpose),
            mode=row.mode,
            total_cells=row.total_cells,
            total_population=float(row.total_population),
            pop_15min=float(row.pop_15min),
            pop_30min=float(row.pop_30min),
            pop_45min=float(row.pop_45min),
            pop_60min=float(row.pop_60min),
            pct_pop_15min=_pct(row.pop_15min, row.total_population),
            pct_pop_30min=_pct(row.pop_30min, row.total_population),
            pct_pop_45min=_pct(row.pop_45min, row.total_population),
            pct_pop_60min=_pct(row.pop_60min, row.total_population),
            avg_travel_time=_f(row.avg_tt),
            median_travel_time=_f(row.median_tt),
        )
        for row in cov_result.fetchall()
    ]

    return AreaDetail(
        name=s.name,
        code=s.code,
        cell_count=s.cell_count,
        population=float(s.population),
        avg_score=_f(s.avg_score),
        weighted_avg_score=_f(s.weighted_avg_score),
        purpose_scores=purpose_scores,
        service_coverage=service_coverage,
    )


@router.get("/comarca/{comarca_code}", response_model=AreaDetail)
def get_comarca_detail(
    comarca_code: str,
    departure_time: str = Query(DEFAULT_DEPARTURE_TIME),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> AreaDetail:
    """Full detail for a specific comarca."""
    dep_time = _validate_departure_time(departure_time)
    return _area_detail(
        table="comarcas",
        code_col="comarca_code",
        code_value=comarca_code,
        dep_time=dep_time,
        tenant=tenant,
        db=db,
    )


@router.get("/municipality/{muni_code}", response_model=AreaDetail)
def get_municipality_detail(
    muni_code: str,
    departure_time: str = Query(DEFAULT_DEPARTURE_TIME),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> AreaDetail:
    """Full detail for a specific municipality."""
    dep_time = _validate_departure_time(departure_time)
    return _area_detail(
        table="municipalities",
        code_col="muni_code",
        code_value=muni_code,
        dep_time=dep_time,
        tenant=tenant,
        db=db,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(v: object) -> float | None:
    """Safely cast a DB value to float or None."""
    return round(float(v), 2) if v is not None else None


def _pct(part: object, total: object) -> float:
    """Compute percentage, returning 0.0 if total is zero."""
    p = float(part) if part is not None else 0.0
    t = float(total) if total is not None else 0.0
    return round(p / t * 100, 1) if t > 0 else 0.0
