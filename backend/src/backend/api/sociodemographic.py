"""Sociodemographic API endpoints.

Serves demographics, income, car ownership, and transit frequency data
for the dashboard enrichment layer.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.api.cells import DEFAULT_DEPARTURE_TIME, _validate_departure_time
from backend.api.schemas import parse_geometry
from backend.auth.deps import get_tenant
from backend.auth.schemas import TenantContext
from backend.db import DuckDBSession, get_db

router = APIRouter(prefix="/sociodemographic", tags=["sociodemographic"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MunicipalityDemographics(BaseModel):
    muni_code: str
    name: str
    year: int
    pop_total: int
    pop_0_17: int
    pop_18_25: int
    pop_26_64: int
    pop_65_plus: int
    pct_0_17: float
    pct_18_25: float
    pct_65_plus: float


class MunicipalityIncome(BaseModel):
    muni_code: str
    name: str
    year: int
    renta_personal_media: float | None
    renta_disponible_media: float | None
    renta_index: float | None


class MunicipalityCarOwnership(BaseModel):
    muni_code: str
    name: str
    year: int
    vehicles_per_inhab: float


class StopFrequencyRecord(BaseModel):
    operator: str
    stop_id: str
    stop_name: str | None
    time_window: str
    departures: int
    departures_per_hour: float
    lon: float
    lat: float


class FrequencyGeoJSON(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict]


class MunicipalitySocioProfile(BaseModel):
    """Combined sociodemographic profile for one municipality."""
    muni_code: str
    name: str
    pop_total: int | None
    pop_0_17: int | None
    pop_18_25: int | None
    pop_65_plus: int | None
    pct_0_17: float | None
    pct_18_25: float | None
    pct_65_plus: float | None
    renta_personal_media: float | None
    renta_disponible_media: float | None
    renta_index: float | None
    vehicles_per_inhab: float | None
    weighted_avg_score: float | None
    population: float | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/demographics", response_model=list[MunicipalityDemographics])
def get_demographics(
    year: int = Query(2025, description="Reference year"),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[MunicipalityDemographics]:
    """Return age-group demographics per municipality."""
    result = db.execute(
        """
        SELECT d.muni_code, COALESCE(m.name, d.muni_code) AS name,
               d.year, d.pop_total, d.pop_0_17, d.pop_18_25,
               d.pop_26_64, d.pop_65_plus,
               d.pct_0_17, d.pct_18_25, d.pct_65_plus
        FROM municipality_demographics d
        LEFT JOIN municipalities m ON m.muni_code = d.muni_code
            AND m.tenant_id = $tenant_id
        WHERE d.year = $year
        ORDER BY d.pop_total DESC
        """,
        {"year": year, "tenant_id": tenant.tenant_id},
    )
    return [MunicipalityDemographics(**row._mapping) for row in result.fetchall()]


@router.get("/income", response_model=list[MunicipalityIncome])
def get_income(
    year: int | None = Query(None, description="Year (latest if omitted)"),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[MunicipalityIncome]:
    """Return income indicators per municipality."""
    if year is None:
        yr_row = db.execute("SELECT MAX(year) FROM municipality_income")
        year = yr_row.scalar() or 2023

    result = db.execute(
        """
        SELECT i.muni_code, COALESCE(m.name, i.muni_code) AS name,
               i.year, i.renta_personal_media,
               i.renta_disponible_media, i.renta_index
        FROM municipality_income i
        LEFT JOIN municipalities m ON m.muni_code = i.muni_code
            AND m.tenant_id = $tenant_id
        WHERE i.year = $year
        ORDER BY i.renta_personal_media DESC NULLS LAST
        """,
        {"year": year, "tenant_id": tenant.tenant_id},
    )
    return [MunicipalityIncome(**row._mapping) for row in result.fetchall()]


@router.get("/car-ownership", response_model=list[MunicipalityCarOwnership])
def get_car_ownership(
    year: int | None = Query(None, description="Year (latest if omitted)"),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[MunicipalityCarOwnership]:
    """Return car ownership rates per municipality."""
    if year is None:
        yr_row = db.execute("SELECT MAX(year) FROM municipality_car_ownership")
        year = yr_row.scalar() or 2023

    result = db.execute(
        """
        SELECT c.muni_code, COALESCE(m.name, c.muni_code) AS name,
               c.year, c.vehicles_per_inhab
        FROM municipality_car_ownership c
        LEFT JOIN municipalities m ON m.muni_code = c.muni_code
            AND m.tenant_id = $tenant_id
        WHERE c.year = $year
        ORDER BY c.vehicles_per_inhab ASC
        """,
        {"year": year, "tenant_id": tenant.tenant_id},
    )
    return [MunicipalityCarOwnership(**row._mapping) for row in result.fetchall()]


@router.get("/frequency/geojson", response_model=FrequencyGeoJSON)
def get_frequency_geojson(
    time_window: str = Query("07:00-09:00", description="Time window"),
    min_dph: float = Query(0, description="Min departures/hour filter"),
    db: DuckDBSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant),
) -> FrequencyGeoJSON:
    """Return stop frequencies as GeoJSON for map overlay."""
    result = db.execute(
        """
        SELECT operator, stop_id, stop_name, departures,
               departures_per_hour,
               ST_X(geom) AS lon, ST_Y(geom) AS lat
        FROM stop_frequency
        WHERE time_window = $tw AND departures_per_hour >= $min_dph
              AND geom IS NOT NULL
        ORDER BY departures_per_hour DESC
        """,
        {"tw": time_window, "min_dph": min_dph},
    )

    features = []
    for row in result.fetchall():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.lon, row.lat],
            },
            "properties": {
                "operator": row.operator,
                "stop_id": row.stop_id,
                "stop_name": row.stop_name,
                "departures": row.departures,
                "departures_per_hour": row.departures_per_hour,
            },
        })

    return FrequencyGeoJSON(features=features)


@router.get("/municipalities/geojson")
def get_municipalities_socio_geojson(
    departure_time: str = Query(
        DEFAULT_DEPARTURE_TIME,
        description="Departure time slot (HH:MM, 30-min intervals)",
    ),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> dict:
    """Return municipalities as GeoJSON with sociodemographic properties for choropleth."""
    dep_time = _validate_departure_time(departure_time)

    # DuckDB supports DISTINCT ON same as PostgreSQL.
    result = db.execute(
        """
        WITH latest_demo AS (
            SELECT DISTINCT ON (muni_code)
                muni_code, pop_total, pct_0_17, pct_18_25, pct_65_plus
            FROM municipality_demographics ORDER BY muni_code, year DESC
        ),
        latest_income AS (
            SELECT DISTINCT ON (muni_code) muni_code, renta_index
            FROM municipality_income ORDER BY muni_code, year DESC
        ),
        latest_cars AS (
            SELECT DISTINCT ON (muni_code) muni_code, vehicles_per_inhab
            FROM municipality_car_ownership ORDER BY muni_code, year DESC
        ),
        muni_scores AS (
            SELECT m.muni_code,
                   CASE WHEN SUM(g.population) > 0
                       THEN SUM(cs.combined_score_normalized * g.population) / SUM(g.population)
                       ELSE AVG(cs.combined_score_normalized)
                   END AS weighted_avg_score
            FROM municipalities m
            JOIN grid_cells g ON g.tenant_id = m.tenant_id AND ST_Intersects(g.centroid, m.geom)
            LEFT JOIN combined_scores cs ON cs.cell_id = g.id AND cs.tenant_id = g.tenant_id
                AND cs.departure_time = $dep_time
            WHERE m.tenant_id = $tenant_id
            GROUP BY m.muni_code
        )
        SELECT m.muni_code, m.name,
               ST_AsGeoJSON(m.geom) AS geometry,
               ms.weighted_avg_score,
               d.pop_total, d.pct_0_17, d.pct_18_25, d.pct_65_plus,
               i.renta_index,
               c.vehicles_per_inhab
        FROM municipalities m
        LEFT JOIN muni_scores ms ON ms.muni_code = m.muni_code
        LEFT JOIN latest_demo d ON d.muni_code = m.muni_code
        LEFT JOIN latest_income i ON i.muni_code = m.muni_code
        LEFT JOIN latest_cars c ON c.muni_code = m.muni_code
        WHERE m.tenant_id = $tenant_id
        """,
        {"tenant_id": tenant.tenant_id, "dep_time": dep_time},
    )

    rows = [row._mapping for row in result.fetchall()]

    # Min-max normalization for vulnerability index
    complete = [
        r for r in rows
        if all(r[k] is not None for k in ["weighted_avg_score", "pct_65_plus", "renta_index", "vehicles_per_inhab"])
    ]

    if complete:
        min_score = min(r["weighted_avg_score"] for r in complete)
        max_score = max(r["weighted_avg_score"] for r in complete)
        min_elderly = min(r["pct_65_plus"] for r in complete)
        max_elderly = max(r["pct_65_plus"] for r in complete)
        min_income = min(r["renta_index"] for r in complete)
        max_income = max(r["renta_index"] for r in complete)
        min_cars = min(r["vehicles_per_inhab"] for r in complete)
        max_cars = max(r["vehicles_per_inhab"] for r in complete)
    else:
        min_score = max_score = 0
        min_elderly = max_elderly = 0
        min_income = max_income = 0
        min_cars = max_cars = 0

    def _norm(v: float, lo: float, hi: float) -> float:
        return (v - lo) / (hi - lo) if hi > lo else 0.0

    features = []
    for r in rows:
        vuln = None
        if r in complete:
            conn_vuln = 1 - _norm(r["weighted_avg_score"], min_score, max_score)
            elderly_vuln = _norm(r["pct_65_plus"], min_elderly, max_elderly)
            income_vuln = 1 - _norm(r["renta_index"], min_income, max_income)
            cars_vuln = 1 - _norm(r["vehicles_per_inhab"], min_cars, max_cars)
            vuln = round(
                conn_vuln * 0.4 + elderly_vuln * 0.2 + income_vuln * 0.2 + cars_vuln * 0.2,
                3,
            )

        features.append({
            "type": "Feature",
            "geometry": parse_geometry(r["geometry"]),
            "properties": {
                "muni_code": r["muni_code"],
                "name": r["name"],
                "pop_total": r["pop_total"],
                "pct_65_plus": round(r["pct_65_plus"], 1) if r["pct_65_plus"] is not None else None,
                "pct_0_17": round(r["pct_0_17"], 1) if r["pct_0_17"] is not None else None,
                "pct_18_25": round(r["pct_18_25"], 1) if r["pct_18_25"] is not None else None,
                "renta_index": round(r["renta_index"], 1) if r["renta_index"] is not None else None,
                "vehicles_per_inhab": round(r["vehicles_per_inhab"], 2) if r["vehicles_per_inhab"] is not None else None,
                "weighted_avg_score": round(r["weighted_avg_score"], 1) if r["weighted_avg_score"] is not None else None,
                "vulnerability": vuln,
            },
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/profiles", response_model=list[MunicipalitySocioProfile])
def get_socio_profiles(
    departure_time: str = Query(
        DEFAULT_DEPARTURE_TIME,
        description="Departure time slot (HH:MM, 30-min intervals)",
    ),
    tenant: TenantContext = Depends(get_tenant),
    db: DuckDBSession = Depends(get_db),
) -> list[MunicipalitySocioProfile]:
    """Return combined sociodemographic + connectivity profile per municipality."""
    dep_time = _validate_departure_time(departure_time)

    result = db.execute(
        """
        WITH latest_demo AS (
            SELECT DISTINCT ON (muni_code)
                muni_code, pop_total, pop_0_17, pop_18_25, pop_65_plus,
                pct_0_17, pct_18_25, pct_65_plus
            FROM municipality_demographics
            ORDER BY muni_code, year DESC
        ),
        latest_income AS (
            SELECT DISTINCT ON (muni_code)
                muni_code, renta_personal_media, renta_disponible_media, renta_index
            FROM municipality_income
            ORDER BY muni_code, year DESC
        ),
        latest_cars AS (
            SELECT DISTINCT ON (muni_code)
                muni_code, vehicles_per_inhab
            FROM municipality_car_ownership
            ORDER BY muni_code, year DESC
        ),
        muni_scores AS (
            SELECT m.muni_code, m.name,
                   SUM(g.population) AS population,
                   CASE WHEN SUM(g.population) > 0
                       THEN SUM(cs.combined_score_normalized * g.population) / SUM(g.population)
                       ELSE AVG(cs.combined_score_normalized)
                   END AS weighted_avg_score
            FROM municipalities m
            JOIN grid_cells g ON g.tenant_id = m.tenant_id
                AND ST_Intersects(g.centroid, m.geom)
            LEFT JOIN combined_scores cs ON cs.cell_id = g.id
                AND cs.tenant_id = g.tenant_id
                AND cs.departure_time = $dep_time
            WHERE m.tenant_id = $tenant_id
            GROUP BY m.muni_code, m.name
        )
        SELECT ms.muni_code, ms.name, ms.population, ms.weighted_avg_score,
               d.pop_total, d.pop_0_17, d.pop_18_25, d.pop_65_plus,
               d.pct_0_17, d.pct_18_25, d.pct_65_plus,
               i.renta_personal_media, i.renta_disponible_media, i.renta_index,
               c.vehicles_per_inhab
        FROM muni_scores ms
        LEFT JOIN latest_demo d ON d.muni_code = ms.muni_code
        LEFT JOIN latest_income i ON i.muni_code = ms.muni_code
        LEFT JOIN latest_cars c ON c.muni_code = ms.muni_code
        ORDER BY ms.population DESC NULLS LAST
        """,
        {"tenant_id": tenant.tenant_id, "dep_time": dep_time},
    )

    return [MunicipalitySocioProfile(**row._mapping) for row in result.fetchall()]
