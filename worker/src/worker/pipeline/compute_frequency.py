"""Compute transit frequency (departures per hour) per stop from raw GTFS data.

Reads stop_times.txt, trips.txt, and calendar.txt from each GTFS zip,
filters to a representative weekday, counts departures per stop in
configurable time windows, and writes results to stop_frequency.parquet.

Output: stop_frequency.parquet (GeoParquet) in the serving directory.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import structlog
from shapely.geometry import Point

logger = structlog.get_logger()

# Default AM peak window
DEFAULT_WINDOWS = [
    ("07:00-09:00", 7 * 60, 9 * 60, 2.0),     # AM peak
    ("09:00-12:00", 9 * 60, 12 * 60, 3.0),     # Mid-morning
    ("12:00-15:00", 12 * 60, 15 * 60, 3.0),    # Midday
    ("15:00-18:00", 15 * 60, 18 * 60, 3.0),    # Afternoon
    ("18:00-21:00", 18 * 60, 21 * 60, 3.0),    # Evening
    ("06:00-22:00", 6 * 60, 22 * 60, 16.0),    # Full day
]


def _parse_time_minutes(time_str: str) -> int | None:
    """Parse GTFS time string (HH:MM:SS) to total minutes.

    GTFS allows hours >= 24 for post-midnight service.
    """
    parts = time_str.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    except ValueError:
        return None


def _get_weekday_service_ids(zf: zipfile.ZipFile) -> set[str]:
    """Extract service_ids that run on a typical weekday (Monday)."""
    names = zf.namelist()
    service_ids: set[str] = set()

    if "calendar.txt" in names:
        with zf.open("calendar.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                # Check monday=1 (typical weekday)
                if row.get("monday", "0") == "1":
                    service_ids.add(row["service_id"])

    # If no calendar.txt or no weekday services found,
    # check calendar_dates.txt for any service
    if not service_ids and "calendar_dates.txt" in names:
        with zf.open("calendar_dates.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                if row.get("exception_type", "1") == "1":
                    service_ids.add(row["service_id"])

    # Last resort: accept all trips
    if not service_ids:
        return set()  # empty means "accept all"

    return service_ids


def _compute_for_feed(
    zf: zipfile.ZipFile,
    operator: str,
    windows: list[tuple[str, int, int, float]],
) -> tuple[list[dict[str, Any]], list[Point]]:
    """Compute departures per hour per stop for one GTFS feed.

    Returns (records, geometries) for building a GeoDataFrame.
    """
    log = logger.bind(operator=operator)
    names = zf.namelist()

    if "stop_times.txt" not in names or "trips.txt" not in names:
        log.warning("frequency_missing_files", available=names)
        return [], []

    # 1. Get weekday services
    weekday_services = _get_weekday_service_ids(zf)
    accept_all = len(weekday_services) == 0
    log.info("frequency_services", weekday_services=len(weekday_services), accept_all=accept_all)

    # 2. Read trips.txt -> map trip_id -> service_id
    trip_service: dict[str, str] = {}
    with zf.open("trips.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        for row in reader:
            trip_service[row["trip_id"]] = row.get("service_id", "")

    # 3. Read stops.txt -> get stop names and coords
    stop_info: dict[str, dict[str, str | float]] = {}
    if "stops.txt" in names:
        with zf.open("stops.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                try:
                    stop_info[row["stop_id"]] = {
                        "name": row.get("stop_name", ""),
                        "lon": float(row["stop_lon"]),
                        "lat": float(row["stop_lat"]),
                    }
                except (ValueError, KeyError):
                    pass

    # 4. Read stop_times.txt and count departures per (stop, window)
    # Structure: {stop_id: {window_label: set(trip_ids)}}
    stop_window_trips: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    with zf.open("stop_times.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        skipped = 0
        processed = 0

        for row in reader:
            trip_id = row.get("trip_id", "")
            service_id = trip_service.get(trip_id, "")

            # Filter to weekday services
            if not accept_all and service_id not in weekday_services:
                skipped += 1
                continue

            dep_str = row.get("departure_time", "")
            dep_min = _parse_time_minutes(dep_str)
            if dep_min is None:
                continue

            stop_id = row.get("stop_id", "")

            # Check each time window
            for window_label, start_min, end_min, _ in windows:
                if start_min <= dep_min < end_min:
                    stop_window_trips[stop_id][window_label].add(trip_id)

            processed += 1

    log.info("frequency_processed", processed=processed, skipped=skipped)

    # 5. Build output records
    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

    for stop_id, window_data in stop_window_trips.items():
        info = stop_info.get(stop_id, {})
        lon = info.get("lon")
        lat = info.get("lat")

        if lon is None or lat is None:
            continue

        for window_label, start_min, end_min, hours in windows:
            trips = window_data.get(window_label, set())
            departures = len(trips)
            dph = departures / hours if hours > 0 else 0

            records.append({
                "operator": operator,
                "stop_id": stop_id,
                "stop_name": info.get("name", ""),
                "time_window": window_label,
                "departures": departures,
                "departures_per_hour": round(dph, 2),
            })
            geometries.append(Point(float(lon), float(lat)))

    return records, geometries


def compute_transit_frequency(
    serving_dir: str | Path,
    gtfs_dir: Path,
    *,
    windows: list[tuple[str, int, int, float]] | None = None,
) -> dict[str, object]:
    """Compute and store transit frequency for all GTFS feeds.

    Writes stop_frequency.parquet as GeoParquet.

    Args:
        serving_dir: Output directory for Parquet files.
        gtfs_dir: Directory containing .gtfs.zip files.
        windows: List of (label, start_minutes, end_minutes, hours) tuples.
    """
    serving = Path(serving_dir)
    log = logger.bind(gtfs_dir=str(gtfs_dir))
    log.info("frequency_compute_start")

    if windows is None:
        windows = DEFAULT_WINDOWS

    zip_files = sorted(gtfs_dir.glob("*.gtfs.zip"))
    # Skip disabled feeds
    zip_files = [z for z in zip_files if not z.name.endswith(".disabled")]

    if not zip_files:
        raise FileNotFoundError(f"No .gtfs.zip files in {gtfs_dir}")

    all_records: list[dict[str, Any]] = []
    all_geoms: list[Point] = []
    operator_counts: dict[str, int] = {}

    for zip_path in zip_files:
        operator = zip_path.stem.replace(".gtfs", "")
        log_op = log.bind(operator=operator)
        log_op.info("frequency_operator_start")

        try:
            with zipfile.ZipFile(zip_path) as zf:
                records, geoms = _compute_for_feed(zf, operator, windows)

            all_records.extend(records)
            all_geoms.extend(geoms)

            operator_counts[operator] = len(records)
            log_op.info("frequency_operator_done", records=len(records))

        except Exception as exc:
            log_op.warning("frequency_operator_failed", error=str(exc))
            operator_counts[operator] = 0

    # Write GeoParquet
    total_inserted = len(all_records)
    if all_records:
        gdf = gpd.GeoDataFrame(all_records, geometry=all_geoms, crs="EPSG:4326")
        out_path = serving / "stop_frequency.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_parquet(out_path)

    log.info("frequency_compute_done", total=total_inserted, operators=len(operator_counts))

    return {
        "total_records": total_inserted,
        "operators": operator_counts,
    }
