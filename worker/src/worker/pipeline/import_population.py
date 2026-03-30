"""Import population data from EUSTAT census sections.

Reads the EUSTAT secciones censales shapefile and the population CSV,
joins them by section code (province + municipality + district + section),
and inserts matched records as population_sources.

Data sources:
  - Shapefile: SECCIONES_EUSTAT_5000_ETRS89.shp (from geo.euskadi.eus)
  - CSV: bizkaia_population_sections.csv (from eustat.eus)
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import structlog
from shapely.geometry import MultiPolygon
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# EUSTAT shapefile CRS is EPSG:25830; we store in 4326.
STORAGE_SRID = 4326

# Bizkaia province code in EUSTAT data
BIZKAIA_PROV = "48"


def parse_population_csv(csv_path: Path) -> dict[str, int]:
    """Parse EUSTAT population CSV and return {section_code: population}.

    The CSV structure (semicolon-delimited, UTF-8):
      - Row 7+: data rows
      - Columns: muni_code; muni_name; district; section; total_pop; ...
      - Section "000" = district/municipal total (skip)

    The join key is: province(2) + municipality(3) + district(2) + section(3)
    """
    sections: dict[str, int] = {}
    current_muni_code: str | None = None
    current_district: str | None = None

    lines = csv_path.read_text(encoding="utf-8").splitlines()

    for line in lines[6:]:  # skip header rows
        line = line.strip()
        if not line:
            continue
        parts = line.split(";")
        if len(parts) < 5:
            continue

        code = parts[0].strip('"').strip()
        district = parts[2].strip('"').strip()
        section = parts[3].strip('"').strip()
        pop_str = parts[4].strip('"').replace(".", "").strip()

        if code:
            current_muni_code = code
        if district:
            current_district = district

        # Skip totals (section "000") and header-only rows
        if not section or section == "000" or current_muni_code is None:
            continue

        try:
            population = int(pop_str)
        except ValueError:
            continue

        join_key = f"{BIZKAIA_PROV}{current_muni_code}{current_district}{section}"
        sections[join_key] = population

    return sections


def load_secciones_shapefile(shp_path: Path) -> gpd.GeoDataFrame:
    """Load EUSTAT secciones shapefile filtered to Bizkaia, reprojected to 4326."""
    gdf = gpd.read_file(shp_path)
    biz = gdf[gdf["SEC_PROV"] == BIZKAIA_PROV].copy()

    # Build join key matching the CSV format
    biz["join_key"] = (
        BIZKAIA_PROV + biz["SEC_MUNI"] + biz["SEC_DIST"] + biz["SEC_SECC"]
    )

    # Fix invalid geometries
    biz["geometry"] = biz.geometry.make_valid()

    # Ensure all geometries are MultiPolygon for schema compatibility
    biz["geometry"] = biz.geometry.apply(_ensure_multi)

    # Reproject to WGS84 for storage
    if biz.crs and biz.crs.to_epsg() != STORAGE_SRID:
        biz = biz.to_crs(epsg=STORAGE_SRID)

    return biz


def _ensure_multi(geom: object) -> MultiPolygon:
    """Promote Polygon to MultiPolygon; pass through MultiPolygon.

    Handles GeometryCollection from make_valid() by extracting all
    polygon parts (both Polygon and MultiPolygon members).
    """
    if geom is None:
        return MultiPolygon()
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    if geom.geom_type == "MultiPolygon":
        return geom
    # GeometryCollection or other — extract all polygon parts
    from shapely.geometry import Polygon

    polys: list[Polygon] = []
    for g in (geom.geoms if hasattr(geom, "geoms") else []):
        if isinstance(g, Polygon):
            polys.append(g)
        elif isinstance(g, MultiPolygon):
            polys.extend(g.geoms)
    return MultiPolygon(polys) if polys else MultiPolygon()


def import_secciones(
    session: Session,
    tenant_id: str,
    shp_path: Path,
    csv_path: Path,
    *,
    clear_existing: bool = True,
) -> dict[str, object]:
    """Import EUSTAT census sections as population_sources.

    Returns statistics including match counts, total population, and
    validation results.
    """
    log = logger.bind(tenant_id=tenant_id)
    log.info("import_secciones_start", shp=str(shp_path), csv=str(csv_path))

    # Parse inputs
    pop_data = parse_population_csv(csv_path)
    gdf = load_secciones_shapefile(shp_path)

    log.info(
        "import_secciones_parsed",
        csv_sections=len(pop_data),
        shp_sections=len(gdf),
    )

    # Match
    matched = []
    unmatched_csv = []
    csv_total_pop = 0

    for code, population in pop_data.items():
        csv_total_pop += population
        rows = gdf[gdf["join_key"] == code]
        if rows.empty:
            unmatched_csv.append(code)
            continue
        row = rows.iloc[0]
        matched.append({
            "code": code,
            "name": row.get("SEC_MUNI_D", ""),
            "population": population,
            "geom_wkt": row.geometry.wkt,
        })

    if unmatched_csv:
        log.warning("import_secciones_unmatched_csv", codes=unmatched_csv)

    # Clear existing population sources if requested
    if clear_existing:
        deleted = session.execute(
            text("DELETE FROM population_sources WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).rowcount
        if deleted:
            log.info("import_secciones_cleared", deleted=deleted)

    # Batch insert
    if matched:
        insert_sql = text("""
            INSERT INTO population_sources (tenant_id, name, population, source_code, geom)
            VALUES (
                :tid,
                :name,
                :pop,
                :code,
                ST_Multi(ST_MakeValid(ST_SetSRID(ST_GeomFromText(:wkt), :srid)))
            )
        """)
        for rec in matched:
            session.execute(insert_sql, {
                "tid": tenant_id,
                "name": rec["name"],
                "pop": rec["population"],
                "code": rec["code"],
                "wkt": rec["geom_wkt"],
                "srid": STORAGE_SRID,
            })

    session.flush()

    # Validate: totals in DB match CSV
    db_total = session.execute(
        text(
            "SELECT COALESCE(SUM(population), 0) "
            "FROM population_sources WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    ).scalar()

    db_count = session.execute(
        text(
            "SELECT COUNT(*) FROM population_sources WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    ).scalar()

    session.commit()

    matched_pop = sum(r["population"] for r in matched)
    loss_pct = abs(csv_total_pop - db_total) / csv_total_pop * 100 if csv_total_pop > 0 else 0

    stats = {
        "csv_sections": len(pop_data),
        "shp_sections": len(gdf),
        "matched": len(matched),
        "unmatched_csv": len(unmatched_csv),
        "csv_total_population": csv_total_pop,
        "matched_population": matched_pop,
        "db_total_population": float(db_total),
        "db_source_count": db_count,
        "loss_pct": round(loss_pct, 4),
    }

    if loss_pct > 0.1:
        log.warning("import_population_loss", **stats)
    else:
        log.info("import_secciones_complete", **stats)

    return stats
