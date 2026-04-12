"""Import travel time matrices produced by the R5R routing container.

R5R writes one Parquet file per (mode, departure slot):
    ttm_transit_0830.parquet  (columns: from_id, to_id, travel_time_p50)
    ttm_walk_0830.parquet     (optional)

Legacy single-time files are also supported:
    ttm_transit.parquet  -> treated as departure_time '08:00'

The mode and departure time are inferred from the filename.

Output: consolidated travel_times.parquet in the serving directory.
"""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import structlog

from worker.io import atomic_write_parquet

logger = structlog.get_logger()

GRID_CRS = "EPSG:25830"  # projected CRS used for grid generation

ALLOWED_MODES = frozenset({"TRANSIT"})
MAX_TRAVEL_TIME = 120.0
DEFAULT_DEPARTURE_TIME = "08:00"

# Matches ttm_{mode}_{HHMM}.parquet or ttm_{mode}.parquet
_FILENAME_RE = re.compile(
    r"^ttm_([a-z]+)(?:_(\d{4}))?\.parquet$", re.IGNORECASE
)


def _parse_filename(name: str) -> tuple[str, str] | None:
    """Extract (mode, departure_time) from a parquet filename.

    Returns None if the filename doesn't match the expected pattern.
    Examples:
        ttm_transit_0830.parquet -> ("TRANSIT", "08:30")
        ttm_transit.parquet      -> ("TRANSIT", "08:00")
    """
    m = _FILENAME_RE.match(name)
    if not m:
        return None
    mode = m.group(1).upper()
    if mode not in ALLOWED_MODES:
        return None
    time_str = m.group(2)
    if time_str:
        hh, mm = int(time_str[:2]), int(time_str[2:])
        departure_time = f"{hh:02d}:{mm:02d}"
    else:
        departure_time = DEFAULT_DEPARTURE_TIME
    return mode, departure_time


def _find_travel_time_column(columns: list[str]) -> str | None:
    """Find the R5R travel-time column.

    R5R names it travel_time_pNN where NN is the requested percentile
    (e.g. travel_time_p50).  Falls back to 'travel_time' if present.
    """
    # Prefer explicit percentile columns
    for col in sorted(columns):
        if col.startswith("travel_time_p"):
            return col
    if "travel_time" in columns:
        return "travel_time"
    return None


def _build_origin_id_remap(
    serving_dir: Path,
    input_dir: Path,
    tenant_id: str,
) -> dict[int, int] | None:
    """Build a mapping from R5R origin IDs to current grid cell IDs.

    R5R's from_id values come from the origins.csv exported before routing.
    If the grid has been rebuilt since then, IDs won't match.  This function
    maps old IDs to new ones by matching coordinates to grid cell_codes.

    Returns None if no remapping is needed (IDs already match).
    """
    log = logger.bind(tenant_id=tenant_id)
    grid_path = serving_dir / "grid_cells.parquet"
    origins_path = input_dir.parent / "network" / "origins.csv"

    if not grid_path.exists() or not origins_path.exists():
        return None

    grid = gpd.read_parquet(grid_path)
    grid_tenant = grid[grid["tenant_id"] == tenant_id]
    if grid_tenant.empty:
        return None

    origins = pd.read_csv(origins_path)
    grid_ids = set(grid_tenant["id"])
    origin_ids = set(origins["id"])

    # Check if IDs already match
    if origin_ids.issubset(grid_ids):
        return None

    log.info("origin_id_remap_building", grid_range=f"{min(grid_ids)}-{max(grid_ids)}",
             origins_range=f"{min(origin_ids)}-{max(origin_ids)}")

    # Convert origins (lon,lat in WGS84) to UTM cell_codes
    origins_gdf = gpd.GeoDataFrame(
        origins,
        geometry=gpd.points_from_xy(origins["lon"], origins["lat"]),
        crs="EPSG:4326",
    ).to_crs(GRID_CRS)

    # Snap each origin centroid to the 250m grid to derive cell_code
    cell_size = 250
    origins["cell_code"] = origins_gdf.geometry.apply(
        lambda pt: f"E{int(np.floor(pt.x / cell_size) * cell_size)}_N{int(np.floor(pt.y / cell_size) * cell_size)}"
    )

    # Build cell_code -> new_id lookup from current grid
    code_to_new_id = dict(zip(grid_tenant["cell_code"], grid_tenant["id"]))

    # Build old_id -> new_id mapping
    remap: dict[int, int] = {}
    for _, row in origins.iterrows():
        new_id = code_to_new_id.get(row["cell_code"])
        if new_id is not None:
            remap[int(row["id"])] = int(new_id)

    log.info("origin_id_remap_complete", mapped=len(remap), total_origins=len(origins))
    return remap if remap else None


def import_travel_times(
    tenant_id: str,
    serving_dir: str | Path,
    input_dir: Path,
) -> dict[str, object]:
    """Import R5R Parquet travel-time matrices into travel_times.parquet.

    Reads ttm_*.parquet files from input_dir.  Mode and departure time
    are inferred from the filename.

    R5R column mapping:
        from_id          -> origin_cell_id
        to_id            -> destination_id
        travel_time_p*   -> travel_time_minutes  (first matching column)

    Returns statistics dict.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, input_dir=str(input_dir))
    log.info("travel_time_import_start")

    parquet_files = sorted(input_dir.glob("ttm_*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"No ttm_*.parquet files found in {input_dir}. "
            "Run the R5R container first."
        )

    all_dfs: list[pd.DataFrame] = []
    total_imported = 0
    total_skipped = 0
    mode_counts: dict[str, int] = {}
    time_slots_seen: set[str] = set()

    for pq_file in parquet_files:
        parsed = _parse_filename(pq_file.name)
        if parsed is None:
            log.warning("skipping_unrecognised_file", file=pq_file.name)
            total_skipped += 1
            continue

        mode, departure_time = parsed

        if mode not in ALLOWED_MODES:
            log.warning("skipping_unknown_mode", file=pq_file.name, mode=mode)
            total_skipped += 1
            continue

        log.info(
            "processing_file",
            file=pq_file.name,
            mode=mode,
            departure_time=departure_time,
        )

        df = pd.read_parquet(pq_file)

        # Find the travel-time column (r5r names it travel_time_pNN)
        tt_col = _find_travel_time_column(df.columns.tolist())
        if tt_col is None:
            log.error(
                "no_travel_time_column",
                file=pq_file.name,
                columns=df.columns.tolist(),
            )
            total_skipped += 1
            continue

        # Rename to canonical form
        df = df.rename(columns={
            "from_id": "origin_cell_id",
            "to_id": "destination_id",
            tt_col: "travel_time_minutes",
        })

        required = {"origin_cell_id", "destination_id", "travel_time_minutes"}
        missing = required - set(df.columns)
        if missing:
            log.error("missing_columns", file=pq_file.name, missing=missing)
            total_skipped += 1
            continue

        # Coerce types — track rows that fail numeric conversion
        before = len(df)

        for col in ("origin_cell_id", "destination_id", "travel_time_minutes"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        coerce_na = df[["origin_cell_id", "destination_id", "travel_time_minutes"]].isna().sum()
        coerce_dropped = int(coerce_na.sum())
        if coerce_dropped:
            log.warning(
                "rows_failed_numeric_coercion",
                file=pq_file.name,
                origin_cell_id_na=int(coerce_na["origin_cell_id"]),
                destination_id_na=int(coerce_na["destination_id"]),
                travel_time_minutes_na=int(coerce_na["travel_time_minutes"]),
            )

        df = df.dropna(subset=["origin_cell_id", "destination_id", "travel_time_minutes"])

        out_of_range = int(((df["travel_time_minutes"] < 0) | (df["travel_time_minutes"] > MAX_TRAVEL_TIME)).sum())
        if out_of_range:
            log.warning(
                "rows_out_of_range",
                file=pq_file.name,
                count=out_of_range,
                max_travel_time=MAX_TRAVEL_TIME,
            )

        df = df[
            (df["travel_time_minutes"] >= 0)
            & (df["travel_time_minutes"] <= MAX_TRAVEL_TIME)
        ]
        skipped = before - len(df)
        total_skipped += skipped

        if df.empty:
            log.warning("no_valid_rows", file=pq_file.name)
            continue

        df["origin_cell_id"] = df["origin_cell_id"].astype(int)
        df["destination_id"] = df["destination_id"].astype(int)

        # Add constant columns
        df["tenant_id"] = tenant_id
        df["mode"] = mode
        df["departure_time"] = departure_time

        # Keep only the columns we need
        df = df[["tenant_id", "origin_cell_id", "destination_id",
                  "mode", "departure_time", "travel_time_minutes"]]

        rows_imported = len(df)
        all_dfs.append(df)

        mode_counts[mode] = mode_counts.get(mode, 0) + rows_imported
        time_slots_seen.add(departure_time)
        total_imported += rows_imported
        log.info(
            "file_imported",
            file=pq_file.name,
            mode=mode,
            departure_time=departure_time,
            rows=rows_imported,
            skipped=skipped,
        )

    # Write consolidated Parquet
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)

        # Remap R5R origin IDs to current grid IDs if they don't match
        remap = _build_origin_id_remap(serving, input_dir, tenant_id)
        if remap:
            before_count = len(combined)
            combined["origin_cell_id"] = combined["origin_cell_id"].map(remap)
            combined = combined.dropna(subset=["origin_cell_id"])
            combined["origin_cell_id"] = combined["origin_cell_id"].astype(int)
            log.info("origin_ids_remapped",
                     rows_before=before_count, rows_after=len(combined))

        out_path = serving / "travel_times.parquet"
        atomic_write_parquet(combined, out_path)

    stats: dict[str, object] = {
        "files_processed": len(parquet_files),
        "rows_imported": total_imported,
        "rows_skipped": total_skipped,
        "mode_counts": mode_counts,
        "departure_times": sorted(time_slots_seen),
    }
    log.info("travel_time_import_complete", **stats)
    return stats
