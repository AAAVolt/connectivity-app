"""Import POI destinations from CSV files in data/pois/.

Supports two CSV formats:

1. **Per-type files** (legacy): filename stem = destination type code.
   Required columns: name, lon, lat. Optional: weight (default 1.0).

2. **Unified file** (e.g. ``all_pois.csv``): a single CSV with a ``poi``
   column that identifies the destination type per row.
   Required columns: poi, nombre, longitud, latitud.
   Optional: weight (default 1.0).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# Bizkaia approximate bounding box for basic validation
LON_MIN, LON_MAX = -3.5, -2.3
LAT_MIN, LAT_MAX = 42.9, 43.5

REQUIRED_COLUMNS_LEGACY = {"name", "lon", "lat"}
REQUIRED_COLUMNS_UNIFIED = {"poi", "nombre", "longitud", "latitud"}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _to_code(raw: str) -> str:
    """Convert a human-readable POI label to a snake_case DB code."""
    return _NON_ALNUM.sub("_", raw.strip().lower()).strip("_")


def _ensure_destination_type(session: Session, code: str, label: str | None = None) -> int:
    """Get or create a destination_type by code, return its id."""
    row = session.execute(
        text("SELECT id FROM destination_types WHERE code = :code"),
        {"code": code},
    ).scalar_one_or_none()
    if row is not None:
        return row

    if label is None:
        label = code.replace("_", " ").title()
    session.execute(
        text(
            "INSERT INTO destination_types (code, label) "
            "VALUES (:code, :label) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {"code": code, "label": label},
    )
    session.flush()
    return session.execute(
        text("SELECT id FROM destination_types WHERE code = :code"),
        {"code": code},
    ).scalar_one()


def _validate_row(
    row: dict[str, str], row_num: int, file_name: str
) -> tuple[str, float, float, float] | None:
    """Validate and parse a single CSV row. Returns (name, lon, lat, weight) or None."""
    name = row.get("name", "").strip()
    lon_str = row.get("lon", "").strip()
    lat_str = row.get("lat", "").strip()
    weight_str = row.get("weight", "").strip()

    if not name:
        logger.warning("poi_import.missing_name", file=file_name, row=row_num)
        return None

    try:
        lon = float(lon_str)
        lat = float(lat_str)
    except (ValueError, TypeError):
        logger.warning(
            "poi_import.invalid_coords",
            file=file_name,
            row=row_num,
            lon=lon_str,
            lat=lat_str,
        )
        return None

    if not (LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX):
        logger.warning(
            "poi_import.coords_outside_bizkaia",
            file=file_name,
            row=row_num,
            lon=lon,
            lat=lat,
        )
        return None

    weight = 1.0
    if weight_str:
        try:
            weight = float(weight_str)
            if weight <= 0:
                logger.warning(
                    "poi_import.invalid_weight",
                    file=file_name,
                    row=row_num,
                    weight=weight_str,
                )
                return None
        except ValueError:
            logger.warning(
                "poi_import.invalid_weight",
                file=file_name,
                row=row_num,
                weight=weight_str,
            )
            return None

    return name, lon, lat, weight


def _is_unified_csv(headers: set[str]) -> bool:
    """Return True if the CSV uses the unified (poi, nombre, longitud, latitud) format."""
    return REQUIRED_COLUMNS_UNIFIED.issubset(headers)


def _import_unified_csv(
    session: Session,
    tenant_id: str,
    csv_path: Path,
    *,
    clear_existing: bool,
    log: structlog.stdlib.BoundLogger,
) -> dict[str, int]:
    """Import a unified CSV where a ``poi`` column identifies the type."""
    results: dict[str, int] = {}
    skipped = 0

    # First pass: if clearing, collect unique types and delete
    if clear_existing:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            type_codes_seen: set[str] = set()
            for row in reader:
                row = {k.strip().lower(): v for k, v in row.items()}
                raw_type = row.get("poi", "").strip()
                if raw_type:
                    type_codes_seen.add(_to_code(raw_type))
        for code in type_codes_seen:
            type_id = _ensure_destination_type(session, code)
            deleted = session.execute(
                text(
                    "DELETE FROM destinations "
                    "WHERE tenant_id = :tid AND type_id = :type_id"
                ),
                {"tid": tenant_id, "type_id": type_id},
            ).rowcount
            if deleted:
                log.info("poi_import.cleared_existing", type_code=code, deleted=deleted)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            row = {k.strip().lower(): v for k, v in row.items()}

            raw_type = row.get("poi", "").strip()
            if not raw_type:
                log.warning("poi_import.missing_poi_type", file=csv_path.name, row=row_num)
                skipped += 1
                continue

            code = _to_code(raw_type)
            # Remap to legacy-style row for validation
            mapped = {
                "name": row.get("nombre", "").strip(),
                "lon": row.get("longitud", "").strip(),
                "lat": row.get("latitud", "").strip(),
                "weight": row.get("weight", "").strip(),
            }
            parsed = _validate_row(mapped, row_num, csv_path.name)
            if parsed is None:
                skipped += 1
                continue

            name, lon, lat, weight = parsed
            type_id = _ensure_destination_type(session, code, label=raw_type)

            session.execute(
                text("""
                    INSERT INTO destinations
                        (tenant_id, type_id, name, geom, weight, metadata)
                    VALUES (
                        :tid, :type_id, :name,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                        :weight, '{}'::jsonb
                    )
                """),
                {
                    "tid": tenant_id,
                    "type_id": type_id,
                    "name": name,
                    "lon": lon,
                    "lat": lat,
                    "weight": weight,
                },
            )
            results[code] = results.get(code, 0) + 1

    session.commit()
    log.info("poi_import.unified_done", imported=results, skipped=skipped)
    return results


def import_pois_from_csv(
    session: Session,
    tenant_id: str,
    pois_dir: Path,
    *,
    clear_existing: bool = False,
) -> dict[str, int]:
    """Import all CSV files from pois_dir into the destinations table.

    Detects the CSV format automatically:
    - If a CSV contains ``poi, nombre, longitud, latitud`` columns it is
      treated as a *unified* file (multiple types in one file).
    - Otherwise the legacy per-type format is used (filename = type code,
      columns: name, lon, lat, weight).

    Args:
        session: SQLAlchemy session.
        tenant_id: Tenant UUID string.
        pois_dir: Directory containing CSV files.
        clear_existing: If True, delete existing destinations for each
            type before inserting.

    Returns:
        Dict mapping destination type code → number of rows imported.
    """
    log = logger.bind(tenant_id=tenant_id, pois_dir=str(pois_dir))

    if not pois_dir.is_dir():
        log.error("poi_import.dir_not_found", path=str(pois_dir))
        raise FileNotFoundError(f"POI directory not found: {pois_dir}")

    csv_files = sorted(pois_dir.glob("*.csv"))
    if not csv_files:
        log.info("poi_import.no_csv_files")
        return {}

    results: dict[str, int] = {}

    for csv_path in csv_files:
        log_file = log.bind(file=csv_path.name)

        # Peek at headers to detect format
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                log_file.warning("poi_import.empty_file")
                continue
            headers = {h.strip().lower() for h in reader.fieldnames}

        if _is_unified_csv(headers):
            log_file.info("poi_import.detected_unified_format")
            file_results = _import_unified_csv(
                session, tenant_id, csv_path,
                clear_existing=clear_existing, log=log_file,
            )
            for code, count in file_results.items():
                results[code] = results.get(code, 0) + count
            continue

        # Legacy per-type format
        type_code = csv_path.stem
        log_file = log_file.bind(type_code=type_code)

        missing = REQUIRED_COLUMNS_LEGACY - headers
        if missing:
            log_file.error(
                "poi_import.missing_columns",
                missing=sorted(missing),
                found=sorted(headers),
            )
            continue

        type_id = _ensure_destination_type(session, type_code)

        if clear_existing:
            deleted = session.execute(
                text(
                    "DELETE FROM destinations "
                    "WHERE tenant_id = :tid AND type_id = :type_id"
                ),
                {"tid": tenant_id, "type_id": type_id},
            ).rowcount
            if deleted:
                log_file.info("poi_import.cleared_existing", deleted=deleted)

        count = 0
        skipped = 0

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                row = {k.strip().lower(): v for k, v in row.items()}
                parsed = _validate_row(row, row_num, csv_path.name)
                if parsed is None:
                    skipped += 1
                    continue

                name, lon, lat, weight = parsed
                session.execute(
                    text("""
                        INSERT INTO destinations
                            (tenant_id, type_id, name, geom, weight, metadata)
                        VALUES (
                            :tid, :type_id, :name,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                            :weight, '{}'::jsonb
                        )
                    """),
                    {
                        "tid": tenant_id,
                        "type_id": type_id,
                        "name": name,
                        "lon": lon,
                        "lat": lat,
                        "weight": weight,
                    },
                )
                count += 1

        session.commit()
        results[type_code] = count
        log_file.info(
            "poi_import.file_done", imported=count, skipped=skipped
        )

    log.info("poi_import.complete", results=results)
    return results
