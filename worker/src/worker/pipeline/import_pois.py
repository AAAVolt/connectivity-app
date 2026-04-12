"""Import POI destinations from CSV files in data/pois/.

Supports two CSV formats:

1. **Per-type files** (legacy): filename stem = destination type code.
   Required columns: name, lon, lat. Optional: weight (default 1.0).

2. **Unified file** (e.g. ``all_pois.csv``): a single CSV with a ``poi``
   column that identifies the destination type per row.
   Required columns: poi, nombre, longitud, latitud.
   Optional: weight (default 1.0).

Output: Appends to destinations.parquet (GeoParquet) in serving_dir.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import structlog
from shapely.geometry import Point

from worker.io import atomic_write_parquet

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


def _ensure_destination_type(
    dest_types_path: Path,
    code: str,
    label: str | None = None,
) -> int:
    """Get or create a destination_type by code, return its id.

    Reads/updates destination_types.parquet.
    """
    if dest_types_path.exists():
        df = pd.read_parquet(dest_types_path)
    else:
        df = pd.DataFrame(columns=["id", "code", "label", "description"])

    match = df[df["code"] == code]
    if not match.empty:
        return int(match.iloc[0]["id"])

    if label is None:
        label = code.replace("_", " ").title()

    new_id = int(df["id"].max()) + 1 if not df.empty else 1
    new_row = pd.DataFrame([{
        "id": new_id,
        "code": code,
        "label": label,
        "description": "",
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    atomic_write_parquet(df, dest_types_path)
    return new_id


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


def _append_destinations(new_gdf: gpd.GeoDataFrame, serving: Path) -> None:
    """Append new destinations to the existing destinations.parquet, or create it.

    Only assigns IDs to newly-added rows, preserving existing IDs so that
    foreign keys in travel_times.parquet remain valid.
    """
    dest_path = serving / "destinations.parquet"
    if dest_path.exists():
        existing = gpd.read_parquet(dest_path)
        max_id = int(existing["id"].max()) if not existing.empty else 0
        new_gdf = new_gdf.copy()
        new_gdf["id"] = range(max_id + 1, max_id + 1 + len(new_gdf))
        combined = pd.concat([existing, new_gdf], ignore_index=True)
        combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    else:
        new_gdf = new_gdf.copy()
        new_gdf["id"] = range(1, len(new_gdf) + 1)
        combined = new_gdf
    atomic_write_parquet(combined, dest_path)


def _remove_destinations_by_type(serving: Path, type_id: int) -> int:
    """Remove destinations with given type_id from destinations.parquet. Returns deleted count."""
    dest_path = serving / "destinations.parquet"
    if not dest_path.exists():
        return 0
    existing = gpd.read_parquet(dest_path)
    before = len(existing)
    filtered = existing[existing["type_id"] != type_id]
    deleted = before - len(filtered)
    if deleted > 0:
        if filtered.empty:
            dest_path.unlink()
        else:
            filtered = gpd.GeoDataFrame(filtered, geometry="geometry", crs="EPSG:4326")
            atomic_write_parquet(filtered, dest_path)
    return deleted


def _import_unified_csv(
    tenant_id: str,
    serving_dir: Path,
    csv_path: Path,
    *,
    clear_existing: bool,
    log: structlog.stdlib.BoundLogger,
) -> dict[str, int]:
    """Import a unified CSV where a ``poi`` column identifies the type."""
    serving = Path(serving_dir)
    dest_types_path = serving / "destination_types.parquet"
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
            type_id = _ensure_destination_type(dest_types_path, code)
            deleted = _remove_destinations_by_type(serving, type_id)
            if deleted:
                log.info("poi_import.cleared_existing", type_code=code, deleted=deleted)

    # Second pass: collect all rows
    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

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
            type_id = _ensure_destination_type(dest_types_path, code, label=raw_type)

            records.append({
                "tenant_id": tenant_id,
                "type_id": type_id,
                "name": name,
                "weight": weight,
                "metadata": "{}",
            })
            geometries.append(Point(lon, lat))
            results[code] = results.get(code, 0) + 1

    if records:
        gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
        _append_destinations(gdf, serving)

    log.info("poi_import.unified_done", imported=results, skipped=skipped)
    return results


def import_pois_from_csv(
    tenant_id: str,
    serving_dir: str | Path,
    pois_dir: Path,
    *,
    clear_existing: bool = False,
) -> dict[str, int]:
    """Import all CSV files from pois_dir into destinations.parquet.

    Detects the CSV format automatically:
    - If a CSV contains ``poi, nombre, longitud, latitud`` columns it is
      treated as a *unified* file (multiple types in one file).
    - Otherwise the legacy per-type format is used (filename = type code,
      columns: name, lon, lat, weight).

    Args:
        tenant_id: Tenant UUID string.
        serving_dir: Directory for output Parquet files.
        pois_dir: Directory containing CSV files.
        clear_existing: If True, delete existing destinations for each
            type before inserting.

    Returns:
        Dict mapping destination type code -> number of rows imported.
    """
    serving = Path(serving_dir)
    dest_types_path = serving / "destination_types.parquet"
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
                tenant_id, serving, csv_path,
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

        type_id = _ensure_destination_type(dest_types_path, type_code)

        if clear_existing:
            deleted = _remove_destinations_by_type(serving, type_id)
            if deleted:
                log_file.info("poi_import.cleared_existing", deleted=deleted)

        count = 0
        skipped = 0
        records: list[dict[str, Any]] = []
        geometries: list[Point] = []

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                row = {k.strip().lower(): v for k, v in row.items()}
                parsed = _validate_row(row, row_num, csv_path.name)
                if parsed is None:
                    skipped += 1
                    continue

                name, lon, lat, weight = parsed
                records.append({
                    "tenant_id": tenant_id,
                    "type_id": type_id,
                    "name": name,
                    "weight": weight,
                    "metadata": "{}",
                })
                geometries.append(Point(lon, lat))
                count += 1

        if records:
            gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
            _append_destinations(gdf, serving)

        results[type_code] = count
        log_file.info(
            "poi_import.file_done", imported=count, skipped=skipped
        )

    log.info("poi_import.complete", results=results)
    return results
