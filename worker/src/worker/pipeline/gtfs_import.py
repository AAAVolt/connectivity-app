"""Import route shapes and stops from downloaded GTFS feeds into the database.

Reads the .gtfs.zip files from the data directory, extracts shapes.txt,
routes.txt, trips.txt, and stops.txt, and writes them as PostGIS geometries.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

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
    session: Session,
    gtfs_dir: Path,
) -> dict[str, dict[str, int]]:
    """Import routes and stops from all GTFS feeds in the directory.

    Returns dict of operator -> {routes: N, stops: N}.
    """
    log = logger.bind(gtfs_dir=str(gtfs_dir))
    log.info("gtfs_import_start")

    zip_files = sorted(gtfs_dir.glob("*.gtfs.zip"))
    if not zip_files:
        raise FileNotFoundError(f"No .gtfs.zip files found in {gtfs_dir}")

    # Clear existing
    session.execute(text("DELETE FROM gtfs_routes"))
    session.execute(text("DELETE FROM gtfs_stops"))

    results: dict[str, dict[str, int]] = {}

    for zip_path in zip_files:
        operator = zip_path.stem.replace(".gtfs", "")
        log_op = log.bind(operator=operator)
        log_op.info("gtfs_import_operator_start")

        try:
            routes_count = _import_routes(session, zip_path, operator)
            stops_count = _import_stops(session, zip_path, operator)
            results[operator] = {"routes": routes_count, "stops": stops_count}
            log_op.info("gtfs_import_operator_complete", routes=routes_count, stops=stops_count)
        except Exception as exc:
            log_op.warning("gtfs_import_operator_failed", error=str(exc))
            results[operator] = {"routes": 0, "stops": 0, "error": str(exc)}  # type: ignore[dict-item]

    session.commit()
    log.info("gtfs_import_complete", operators=len(results))
    return results


def _import_stops(session: Session, zip_path: Path, operator: str) -> int:
    """Extract and import stops from a GTFS zip."""
    with zipfile.ZipFile(zip_path) as zf:
        if "stops.txt" not in zf.namelist():
            return 0

        with zf.open("stops.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            batch: list[dict[str, object]] = []
            count = 0

            for row in reader:
                try:
                    lon = float(row["stop_lon"])
                    lat = float(row["stop_lat"])
                except (ValueError, KeyError):
                    continue

                batch.append({
                    "operator": operator,
                    "stop_id": row.get("stop_id", ""),
                    "stop_name": row.get("stop_name", ""),
                    "lon": lon,
                    "lat": lat,
                })
                count += 1

                if len(batch) >= 1000:
                    _insert_stops_batch(session, batch)
                    batch = []

            if batch:
                _insert_stops_batch(session, batch)

    return count


def _insert_stops_batch(session: Session, batch: list[dict[str, object]]) -> None:
    session.execute(
        text("""
            INSERT INTO gtfs_stops (operator, stop_id, stop_name, geom)
            VALUES (:operator, :stop_id, :stop_name,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ON CONFLICT (operator, stop_id) DO NOTHING
        """),
        batch,
    )


def _import_routes(session: Session, zip_path: Path, operator: str) -> int:
    """Extract and import route shapes from a GTFS zip.

    Builds LineStrings from shapes.txt, links them to routes via trips.txt,
    and stores one MultiLineString per route.
    """
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

        # Read trips.txt to map shape_id → route_id
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
            # No shapes — try to build routes from stop sequences instead
            return 0

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

        # Group shapes by route_id and build WKT MultiLineStrings
        route_shapes: dict[str, list[list[tuple[float, float]]]] = defaultdict(list)
        for shape_id, points in shape_points.items():
            route_id = shape_to_route.get(shape_id, shape_id)
            # Sort by sequence and extract coords
            points.sort(key=lambda p: p[0])
            coords = [(lon, lat) for _, lon, lat in points]
            if len(coords) >= 2:
                route_shapes[route_id].append(coords)

        # Deduplicate shapes per route (keep unique ones only)
        count = 0
        for route_id, line_lists in route_shapes.items():
            # Build a single representative line per route (first shape)
            # to avoid massive geometries
            info = routes_info.get(route_id, {})
            wkt_lines = []
            seen_signatures: set[tuple[float, ...]] = set()
            for coords in line_lists:
                # Simple dedup: use first and last points as signature
                sig = (coords[0][0], coords[0][1], coords[-1][0], coords[-1][1])
                if sig in seen_signatures:
                    continue
                seen_signatures.add(sig)
                wkt_coords = ",".join(f"{lon} {lat}" for lon, lat in coords)
                wkt_lines.append(f"({wkt_coords})")

            if not wkt_lines:
                continue

            wkt = f"MULTILINESTRING({','.join(wkt_lines)})"

            session.execute(
                text("""
                    INSERT INTO gtfs_routes (operator, route_id, route_name, route_type, route_color, geom)
                    VALUES (:operator, :route_id, :route_name, :route_type, :route_color,
                            ST_SetSRID(ST_GeomFromText(:wkt), 4326))
                    ON CONFLICT (operator, route_id) DO UPDATE
                    SET route_name = EXCLUDED.route_name,
                        route_type = EXCLUDED.route_type,
                        route_color = EXCLUDED.route_color,
                        geom = EXCLUDED.geom
                """),
                {
                    "operator": operator,
                    "route_id": route_id,
                    "route_name": info.get("name", ""),
                    "route_type": int(info.get("type", "3")),
                    "route_color": info.get("color", ""),
                    "wkt": wkt,
                },
            )
            count += 1

    return count
