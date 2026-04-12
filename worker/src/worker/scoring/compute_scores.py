"""Compute connectivity and combined scores for all grid cells.

Uses DuckDB as a transient query engine over Parquet files.
Processes travel times in batches to avoid OOM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import structlog

from worker.db import create_engine, register_parquet
from worker.io import atomic_write_parquet
from worker.scoring.config import ScoringConfig, load_scoring_config
from worker.scoring.diminishing import concave_transform
from worker.scoring.impedance import exponential_impedance

logger = structlog.get_logger()

BATCH_SIZE = 5000
CELL_CHUNK = 10_000


def compute_scores(
    tenant_id: str,
    serving_dir: str | Path,
    raw_dir: str | Path | None = None,
    config: ScoringConfig | None = None,
    departure_time: str | None = None,
) -> dict[str, object]:
    """Compute connectivity scores for all grid cells of a tenant.

    Reads travel times from Parquet (either serving_dir or raw_dir),
    computes impedance-weighted accessibility scores, normalises,
    and writes results as Parquet to serving_dir.
    """
    if config is None:
        config = load_scoring_config()

    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id)
    log.info("scoring_start")

    # Set up DuckDB engine with all required tables
    conn = create_engine()

    # Register travel times
    tt_path = serving / "travel_times.parquet"
    if raw_dir:
        raw = Path(raw_dir)
        if raw.is_dir() and any(raw.glob("ttm_*.parquet")):
            register_parquet(conn, "travel_times", raw)
        elif tt_path.exists():
            register_parquet(conn, "travel_times", tt_path)
    elif tt_path.exists():
        register_parquet(conn, "travel_times", tt_path)
    else:
        raise FileNotFoundError(
            f"No travel times found in {serving} or {raw_dir}"
        )

    # Register other required tables — fail early with clear message
    for table in ("destinations", "destination_types", "grid_cells"):
        path = serving / f"{table}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"Required file {path} not found. "
                f"Ensure the import pipeline has run before scoring."
            )
        register_parquet(conn, table, path)

    # Discover departure time slots
    if departure_time is not None:
        slots = [departure_time]
    else:
        rows = conn.execute(
            """
            SELECT DISTINCT departure_time
            FROM travel_times
            WHERE tenant_id = $tid
            ORDER BY departure_time
            """,
            {"tid": tenant_id},
        ).fetchall()
        slots = [r[0] for r in rows]
        if not slots:
            raise ValueError(
                f"No departure time slots found in travel_times for tenant {tenant_id}. "
                "Ensure travel times have been imported before scoring."
            )

    log.info("scoring_slots", count=len(slots), slots=slots)

    total_scores = 0
    total_combined = 0
    total_min_tt = 0

    all_score_dfs: list[pd.DataFrame] = []
    all_combined_dfs: list[pd.DataFrame] = []
    all_min_tt_dfs: list[pd.DataFrame] = []

    for slot in slots:
        log.info("scoring_slot_start", departure_time=slot)
        result = _compute_for_slot(conn, tenant_id, slot, config, log)
        total_scores += len(result["scores_df"])
        total_combined += len(result["combined_df"])
        total_min_tt += len(result["min_tt_df"])
        all_score_dfs.append(result["scores_df"])
        all_combined_dfs.append(result["combined_df"])
        all_min_tt_dfs.append(result["min_tt_df"])

    conn.close()

    # Write results as Parquet (atomic to avoid corruption on crash)
    if all_score_dfs:
        scores_df = pd.concat(all_score_dfs, ignore_index=True)
        atomic_write_parquet(scores_df, serving / "connectivity_scores.parquet")

    if all_combined_dfs:
        combined_df = pd.concat(all_combined_dfs, ignore_index=True)
        atomic_write_parquet(combined_df, serving / "combined_scores.parquet")

    if all_min_tt_dfs:
        min_tt_df = pd.concat(all_min_tt_dfs, ignore_index=True)
        atomic_write_parquet(min_tt_df, serving / "min_travel_times.parquet")

    result_stats: dict[str, object] = {
        "scores_written": total_scores,
        "combined_written": total_combined,
        "min_travel_times_written": total_min_tt,
        "departure_times": slots,
    }
    log.info("scoring_complete", **result_stats)
    return result_stats


def _compute_for_slot(
    conn: object,
    tenant_id: str,
    departure_time: str,
    config: ScoringConfig,
    log: structlog.stdlib.BoundLogger,
) -> dict[str, pd.DataFrame]:
    """Compute scores for a single departure_time slot."""

    # Discover origin cells for this slot
    cell_ids = [
        r[0]
        for r in conn.execute(
            """
            SELECT DISTINCT origin_cell_id
            FROM travel_times
            WHERE tenant_id = $tid AND departure_time = $dep_time
            ORDER BY origin_cell_id
            """,
            {"tid": tenant_id, "dep_time": departure_time},
        ).fetchall()
    ]

    empty = {
        "scores_df": pd.DataFrame(),
        "combined_df": pd.DataFrame(),
        "min_tt_df": pd.DataFrame(),
    }

    if not cell_ids:
        log.warning("no_travel_times_found", departure_time=departure_time)
        return empty

    log.info("scoring_cells_found", count=len(cell_ids))

    # Fetch travel times in chunks
    all_scores: list[pd.DataFrame] = []
    all_min_tt: list[pd.DataFrame] = []

    for i in range(0, len(cell_ids), CELL_CHUNK):
        chunk_ids = cell_ids[i : i + CELL_CHUNK]
        log.info("scoring_chunk", offset=i, size=len(chunk_ids))

        # Create temp table for chunk IDs
        conn.execute("CREATE OR REPLACE TEMP TABLE chunk_ids AS SELECT UNNEST($ids) AS id",
                      {"ids": chunk_ids})

        rows = conn.execute(
            """
            SELECT
                tt.origin_cell_id,
                tt.mode,
                dt.code AS dest_type,
                tt.travel_time_minutes,
                d.weight
            FROM travel_times tt
            JOIN destinations d ON tt.destination_id = d.id
            JOIN destination_types dt ON d.type_id = dt.id
            JOIN chunk_ids ci ON tt.origin_cell_id = ci.id
            WHERE tt.tenant_id = $tid
              AND tt.departure_time = $dep_time
              AND tt.travel_time_minutes <= $max_tt
            """,
            {
                "tid": tenant_id,
                "dep_time": departure_time,
                "max_tt": config.max_travel_time,
            },
        ).fetchall()

        if not rows:
            continue

        df = pd.DataFrame(
            rows, columns=["cell_id", "mode", "dest_type", "travel_time", "weight"]
        )

        # Map destination type -> purpose
        df["purpose"] = df["dest_type"].map(config.purpose_map)
        unmapped_mask = df["purpose"].isna()
        if unmapped_mask.any():
            unmapped_types = df.loc[unmapped_mask, "dest_type"].unique().tolist()
            log.warning(
                "unmapped_destination_types",
                types=unmapped_types,
                rows_dropped=int(unmapped_mask.sum()),
            )
        df = df.dropna(subset=["purpose"])
        if df.empty:
            continue

        # Impedance
        def _contribution(row: pd.Series) -> float:
            alpha = config.impedance.get(row["mode"], {}).get(row["purpose"], 0.05)
            return float(row["weight"]) * exponential_impedance(
                float(row["travel_time"]), alpha
            )

        df["contribution"] = df.apply(_contribution, axis=1)

        # Aggregate per (cell, mode, purpose)
        grouped = (
            df.groupby(["cell_id", "mode", "purpose"])["contribution"]
            .sum()
            .reset_index()
            .rename(columns={"contribution": "raw_score"})
        )
        grouped["score"] = grouped["raw_score"].apply(
            lambda x: concave_transform(x, config.beta)
        )
        all_scores.append(grouped)

        # Min travel times
        rows_full = conn.execute(
            """
            SELECT
                tt.origin_cell_id,
                tt.mode,
                dt.code AS dest_type,
                tt.travel_time_minutes,
                tt.destination_id
            FROM travel_times tt
            JOIN destinations d ON tt.destination_id = d.id
            JOIN destination_types dt ON d.type_id = dt.id
            JOIN chunk_ids ci ON tt.origin_cell_id = ci.id
            WHERE tt.tenant_id = $tid
              AND tt.departure_time = $dep_time
              AND tt.travel_time_minutes <= $max_tt
            """,
            {
                "tid": tenant_id,
                "dep_time": departure_time,
                "max_tt": config.max_travel_time,
            },
        ).fetchall()

        df_full = pd.DataFrame(
            rows_full,
            columns=["cell_id", "mode", "dest_type", "travel_time", "destination_id"],
        )
        df_full["purpose"] = df_full["dest_type"].map(config.purpose_map)
        df_full = df_full.dropna(subset=["purpose"])

        if not df_full.empty:
            min_tt = (
                df_full.loc[
                    df_full.groupby(["cell_id", "mode", "purpose"])["travel_time"].idxmin()
                ][["cell_id", "mode", "purpose", "travel_time", "destination_id"]]
                .reset_index(drop=True)
            )
            all_min_tt.append(min_tt)

    if not all_scores:
        log.warning("no_mapped_purposes", departure_time=departure_time)
        return empty

    # Concatenate chunks
    grouped = pd.concat(all_scores, ignore_index=True)
    min_tt_all = pd.concat(all_min_tt, ignore_index=True) if all_min_tt else pd.DataFrame()

    # Normalise per (mode, purpose) to [0, 100]
    def _normalize(group: pd.DataFrame) -> pd.DataFrame:
        mn, mx = group["score"].min(), group["score"].max()
        out = group.copy()
        out["score_normalized"] = (
            50.0 if mx == mn else (out["score"] - mn) / (mx - mn) * 100.0
        )
        return out

    grouped = grouped.groupby(
        ["mode", "purpose"], group_keys=False
    ).apply(_normalize)

    # Build connectivity_scores DataFrame
    scores_df = grouped[["cell_id", "mode", "purpose", "score", "score_normalized"]].copy()
    scores_df["tenant_id"] = tenant_id
    scores_df["departure_time"] = departure_time
    scores_df["id"] = range(1, len(scores_df) + 1)

    # Build min_travel_times DataFrame
    if not min_tt_all.empty:
        min_tt_df = min_tt_all.rename(columns={
            "travel_time": "min_travel_time_minutes",
            "destination_id": "nearest_destination_id",
        })
        min_tt_df["tenant_id"] = tenant_id
        min_tt_df["departure_time"] = departure_time
        min_tt_df["id"] = range(1, len(min_tt_df) + 1)
    else:
        min_tt_df = pd.DataFrame()

    # Combined scores — normalise weights so only purposes present in the
    # data contribute and their effective weights sum to 1.0 per mode.
    present_purposes = set(grouped[["mode", "purpose"]].itertuples(index=False, name=None))
    weights_rows = []
    for mode, purposes in config.combined_weights.items():
        active = {p: w for p, w in purposes.items() if (mode, p) in present_purposes}
        total = sum(active.values())
        if total <= 0:
            continue
        for purpose, w in active.items():
            weights_rows.append({"mode": mode, "purpose": purpose, "w": w / total})
    weights_df = pd.DataFrame(weights_rows)

    merged = grouped.merge(weights_df, on=["mode", "purpose"], how="inner")
    merged["weighted"] = merged["score_normalized"] * merged["w"]

    combined = merged.groupby("cell_id")["weighted"].sum().reset_index()
    combined.columns = ["cell_id", "combined_score"]

    c_min, c_max = combined["combined_score"].min(), combined["combined_score"].max()
    combined["combined_score_normalized"] = (
        50.0 if c_max == c_min
        else (combined["combined_score"] - c_min) / (c_max - c_min) * 100.0
    )

    combined["tenant_id"] = tenant_id
    combined["departure_time"] = departure_time
    combined["weights"] = json.dumps(config.combined_weights)
    combined["id"] = range(1, len(combined) + 1)

    log.info(
        "scoring_slot_complete",
        departure_time=departure_time,
        scores=len(scores_df),
        combined=len(combined),
        min_tt=len(min_tt_df),
    )

    return {
        "scores_df": scores_df,
        "combined_df": combined,
        "min_tt_df": min_tt_df,
    }
