"""Import route shapes and stops from downloaded GTFS feeds.

Reads the .gtfs.zip files from the data directory, extracts shapes.txt,
routes.txt, trips.txt, and stops.txt, and writes them as GeoParquet.

Output: gtfs_routes.parquet + gtfs_stops.parquet in the serving directory.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import structlog
from shapely.geometry import MultiLineString, Point
from shapely import wkt as shapely_wkt

logger = structlog.get_logger()

# GTFS route_type mapping for display
ROUTE_TYPE_LABELS = {
    0: "Tram",
    1: "Metro",
    2: "Rail",
    3: "Bus",
    4: "Ferry",
    5: "Cable car",
    6: "Gondola",
    7: "Funicular",
}


def import_gtfs_to_db(
    serving_dir: str | Path,
    gtfs_dir: Path,
) -> dict[str, dict[str, int]]:
    """Import routes and stops from all GTFS feeds in the directory.

    Writes gtfs_routes.parquet and gtfs_stops.parquet as GeoParquet.
    Returns dict of operator -> {routes: N, stops: N}.
    """
    serving = Path(serving_dir)
    log = logger.bind(gtfs_dir=str(gtfs_dir))
    log.info("gtfs_import_start")

    zip_files = sorted(gtfs_dir.glob("*.gtfs.zip"))
    if not zip_files:
        raise FileNotFoundError(f"No .gtfs.zip files found in {gtfs_dir}")

    all_route_records: list[dict[str, Any]] = []
    all_route_geoms: list[MultiLineString] = []
    all_stop_records: list[dict[str, Any]] = []
    all_stop_geoms: list[Point] = []

    results: dict[str, dict[str, int]] = {}

    for zip_path in zip_files:
        operator = zip_path.stem.replace(".gtfs", "")
        log_op = log.bind(operator=operator)
        log_op.info("gtfs_import_operator_start")

        try:
            route_recs, route_geoms = _extract_routes(zip_path, operator)
            stop_recs, stop_geoms = _extract_stops(zip_path, operator)

            all_route_records.extend(route_recs)
            all_route_geoms.extend(route_geoms)
            all_stop_records.extend(stop_recs)
            all_stop_geoms.extend(stop_geoms)

            results[operator] = {"routes": len(route_recs), "stops": len(stop_recs)}
            log_op.info("gtfs_import_operator_complete", routes=len(route_recs), stops=len(stop_recs))
        except Exception as exc:
            log_op.warning("gtfs_import_operator_failed", error=str(exc))
            results[operator] = {"routes": 0, "stops": 0, "error": str(exc)}  # type: ignore[dict-item]

    # Write GeoParquet files
    if all_route_records:
        routes_gdf = gpd.GeoDataFrame(
            all_route_records, geometry=all_route_geoms, crs="EPSG:4326"
        )
        out_path = serving / "gtfs_routes.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        routes_gdf.to_parquet(out_path)

    if all_stop_records:
        stops_gdf = gpd.GeoDataFrame(
            all_stop_records, geometry=all_stop_geoms, crs="EPSG:4326"
        )
        out_path = serving / "gtfs_stops.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        stops_gdf.to_parquet(out_path)

    log.info("gtfs_import_complete", operators=len(results))
    return results


def _extract_stops(
    zip_path: Path, operator: str
) -> tuple[list[dict[str, Any]], list[Point]]:
    """Extract stops from a GTFS zip. Returns (records, geometries)."""
    records: list[dict[str, Any]] = []
    geometries: list[Point] = []

    with zipfile.ZipFile(zip_path) as zf:
        if "stops.txt" not in zf.namelist():
            return records, geometries

        with zf.open("stops.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

            for row in reader:
                try:
                    lon = float(row["stop_lon"])
                    lat = float(row["stop_lat"])
                except (ValueError, KeyError):
                    continue

                records.append({
                    "operator": operator,
                    "stop_id": row.get("stop_id", ""),
                    "stop_name": row.get("stop_name", ""),
                })
                geometries.append(Point(lon, lat))

    return records, geometries


def _extract_routes(
    zip_path: Path, operator: str
) -> tuple[list[dict[str, Any]], list[MultiLineString]]:
    """Extract route shapes from a GTFS zip. Returns (records, geometries).

    Builds LineStrings from shapes.txt, links them to routes via trips.txt,
    and produces one MultiLineString per route.
    """
    records: list[dict[str, Any]] = []
    geometries: list[MultiLineString] = []

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

        # Read routes.txt
        routes_info: dict[str, dict[str, str]] = {}
        if "routes.txt" in names:
            with zf.open("routes.txt") as f:
                for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                    routes_info[row.get("route_id", "")] = {
                        "name": row.get("route_long_name") or row.get("route_short_name", ""),
                        "type": row.get("route_type", "3"),
                        "color": row.get("route_color", ""),
                    }

        # Read trips.txt to map shape_id -> route_id
        shape_to_route: dict[str, str] = {}
        if "trips.txt" in names:
            with zf.open("trips.txt") as f:
                for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                    sid = row.get("shape_id", "")
                    rid = row.get("route_id", "")
                    if sid and rid:
                        shape_to_route[sid] = rid

        # Read shapes.txt and group points by shape_id
        if "shapes.txt" not in names:
            return records, geometries

        shape_points: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
        with zf.open("shapes.txt") as f:
            for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                try:
                    sid = row["shape_id"]
                    lon = float(row["shape_pt_lon"])
                    lat = float(row["shape_pt_lat"])
                    seq = float(row.get("shape_pt_sequence", 0))
                    shape_points[sid].append((seq, lon, lat))
                except (ValueError, KeyError):
                    continue

        # Group shapes by route_id and build MultiLineStrings
        route_shapes: dict[str, list[list[tuple[float, float]]]] = defaultdict(list)
        for shape_id, points in shape_points.items():
            route_id = shape_to_route.get(shape_id, shape_id)
            # Sort by sequence and extract coords
            points.sort(key=lambda p: p[0])
            coords = [(lon, lat) for _, lon, lat in points]
            if len(coords) >= 2:
                route_shapes[route_id].append(coords)

        # Deduplicate shapes per route (keep unique ones only)
        for route_id, line_lists in route_shapes.items():
            info = routes_info.get(route_id, {})
            unique_lines: list[list[tuple[float, float]]] = []
            seen_signatures: set[tuple[float, ...]] = set()

            for coords in line_lists:
                # Simple dedup: use first and last points as signature
                sig = (coords[0][0], coords[0][1], coords[-1][0], coords[-1][1])
                if sig in seen_signatures:
                    continue
                seen_signatures.add(sig)
                unique_lines.append(coords)

            if not unique_lines:
                continue

            multi_line = MultiLineString(unique_lines)

            records.append({
                "operator": operator,
                "route_id": route_id,
                "route_name": info.get("name", ""),
                "route_type": int(info.get("type", "3")),
                "route_color": info.get("color", ""),
            })
            geometries.append(multi_line)

    return records, geometries
