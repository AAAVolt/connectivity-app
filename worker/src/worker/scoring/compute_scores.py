"""Compute connectivity and combined scores for all grid cells.

Processes travel times in batches of origin cells to avoid OOM
when the full OD matrix is tens of millions of rows.
"""

from __future__ import annotations

import json

import pandas as pd
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.scoring.config import ScoringConfig, load_scoring_config
from worker.scoring.diminishing import concave_transform
from worker.scoring.impedance import exponential_impedance

logger = structlog.get_logger()

BATCH_SIZE = 5000
# Number of origin cells to fetch per scoring chunk (keeps memory bounded).
CELL_CHUNK = 10_000


def compute_scores(
    session: Session,
    tenant_id: str,
    config: ScoringConfig | None = None,
    departure_time: str | None = None,
) -> dict[str, object]:
    """Compute connectivity scores for all grid cells of a tenant.

    If departure_time is given (e.g. "08:00"), computes for that slot only.
    If None, discovers all distinct departure_times in travel_times and
    computes for each.
    """
    if config is None:
        config = load_scoring_config()

    log = logger.bind(tenant_id=tenant_id)
    log.info("scoring_start")

    if departure_time is not None:
        slots = [departure_time]
    else:
        rows = session.execute(
            text("""
                SELECT DISTINCT departure_time
                FROM travel_times
                WHERE tenant_id = :tid
                ORDER BY departure_time
            """),
            {"tid": tenant_id},
        ).fetchall()
        slots = [r[0] for r in rows]
        if not slots:
            slots = ["08:00"]

    log.info("scoring_slots", count=len(slots), slots=slots)

    total_scores = 0
    total_combined = 0
    total_min_tt = 0

    for slot in slots:
        log.info("scoring_slot_start", departure_time=slot)
        stats = _compute_for_slot(session, tenant_id, slot, config, log)
        total_scores += stats["scores_written"]
        total_combined += stats["combined_written"]
        total_min_tt += stats["min_travel_times_written"]

    session.commit()

    result: dict[str, object] = {
        "scores_written": total_scores,
        "combined_written": total_combined,
        "min_travel_times_written": total_min_tt,
        "departure_times": slots,
    }
    log.info("scoring_complete", **result)
    return result


def _compute_for_slot(
    session: Session,
    tenant_id: str,
    departure_time: str,
    config: ScoringConfig,
    log: structlog.stdlib.BoundLogger,
) -> dict[str, int]:
    """Compute scores for a single departure_time slot.

    Fetches travel times in chunks of CELL_CHUNK origin cells to keep
    memory usage bounded, then aggregates and normalises across all cells.
    """

    # ── 0. Discover distinct origin cells for this slot ──
    cell_ids = [
        r[0]
        for r in session.execute(
            text("""
                SELECT DISTINCT origin_cell_id
                FROM travel_times
                WHERE tenant_id = :tid AND departure_time = :dep_time
                ORDER BY origin_cell_id
            """),
            {"tid": tenant_id, "dep_time": departure_time},
        ).fetchall()
    ]

    if not cell_ids:
        log.warning("no_travel_times_found", departure_time=departure_time)
        return {"scores_written": 0, "combined_written": 0, "min_travel_times_written": 0}

    log.info("scoring_cells_found", count=len(cell_ids))

    # ── 1. Fetch travel times in chunks and compute per-cell raw scores ──
    all_scores: list[pd.DataFrame] = []
    all_min_tt: list[pd.DataFrame] = []

    for i in range(0, len(cell_ids), CELL_CHUNK):
        chunk_ids = cell_ids[i : i + CELL_CHUNK]
        log.info("scoring_chunk", offset=i, size=len(chunk_ids))

        # Fetch with weights
        rows = session.execute(
            text("""
                SELECT
                    tt.origin_cell_id,
                    tt.mode,
                    dt.code AS dest_type,
                    tt.travel_time_minutes,
                    d.weight
                FROM travel_times tt
                JOIN destinations d ON tt.destination_id = d.id
                JOIN destination_types dt ON d.type_id = dt.id
                WHERE tt.tenant_id = :tid
                  AND tt.departure_time = :dep_time
                  AND tt.travel_time_minutes <= :max_tt
                  AND tt.origin_cell_id = ANY(:cell_ids)
            """),
            {
                "tid": tenant_id,
                "dep_time": departure_time,
                "max_tt": config.max_travel_time,
                "cell_ids": chunk_ids,
            },
        ).fetchall()

        if not rows:
            continue

        df = pd.DataFrame(
            rows, columns=["cell_id", "mode", "dest_type", "travel_time", "weight"]
        )

        # Map destination type → purpose
        df["purpose"] = df["dest_type"].map(config.purpose_map)
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

        # Min travel times (with destination_id)
        rows_full = session.execute(
            text("""
                SELECT
                    tt.origin_cell_id,
                    tt.mode,
                    dt.code AS dest_type,
                    tt.travel_time_minutes,
                    tt.destination_id
                FROM travel_times tt
                JOIN destinations d ON tt.destination_id = d.id
                JOIN destination_types dt ON d.type_id = dt.id
                WHERE tt.tenant_id = :tid
                  AND tt.departure_time = :dep_time
                  AND tt.travel_time_minutes <= :max_tt
                  AND tt.origin_cell_id = ANY(:cell_ids)
            """),
            {
                "tid": tenant_id,
                "dep_time": departure_time,
                "max_tt": config.max_travel_time,
                "cell_ids": chunk_ids,
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
        return {"scores_written": 0, "combined_written": 0, "min_travel_times_written": 0}

    # ── 2. Concatenate all chunks ──
    grouped = pd.concat(all_scores, ignore_index=True)
    min_tt_all = pd.concat(all_min_tt, ignore_index=True) if all_min_tt else pd.DataFrame()

    # ── 3. Normalise per (mode, purpose) to [0, 100] ──
    def _normalize(group: pd.DataFrame) -> pd.DataFrame:
        mn, mx = group["score"].min(), group["score"].max()
        out = group.copy()
        if mx == mn:
            out["score_normalized"] = 0.0
        else:
            out["score_normalized"] = (out["score"] - mn) / (mx - mn) * 100.0
        return out

    grouped = grouped.groupby(
        ["mode", "purpose"], group_keys=False
    ).apply(_normalize)

    # ── 4. Write connectivity_scores ──
    session.execute(
        text(
            "DELETE FROM connectivity_scores "
            "WHERE tenant_id = :tid AND departure_time = :dep_time"
        ),
        {"tid": tenant_id, "dep_time": departure_time},
    )

    records = grouped.to_dict("records")
    for i in range(0, len(records), BATCH_SIZE):
        batch = [
            {
                "tenant_id": tenant_id,
                "cell_id": int(r["cell_id"]),
                "mode": r["mode"],
                "purpose": r["purpose"],
                "score": float(r["score"]),
                "score_normalized": float(r["score_normalized"]),
                "departure_time": departure_time,
            }
            for r in records[i : i + BATCH_SIZE]
        ]
        session.execute(
            text("""
                INSERT INTO connectivity_scores
                    (tenant_id, cell_id, mode, purpose, score,
                     score_normalized, departure_time)
                VALUES
                    (:tenant_id, :cell_id, :mode, :purpose, :score,
                     :score_normalized, :departure_time)
            """),
            batch,
        )

    # ── 4b. Write min travel times ──
    session.execute(
        text(
            "DELETE FROM min_travel_times "
            "WHERE tenant_id = :tid AND departure_time = :dep_time"
        ),
        {"tid": tenant_id, "dep_time": departure_time},
    )

    if not min_tt_all.empty:
        min_records = min_tt_all.to_dict("records")
        for i in range(0, len(min_records), BATCH_SIZE):
            batch = [
                {
                    "tenant_id": tenant_id,
                    "cell_id": int(r["cell_id"]),
                    "mode": r["mode"],
                    "purpose": r["purpose"],
                    "min_tt": float(r["travel_time"]),
                    "dest_id": int(r["destination_id"]),
                    "departure_time": departure_time,
                }
                for r in min_records[i : i + BATCH_SIZE]
            ]
            session.execute(
                text("""
                    INSERT INTO min_travel_times
                        (tenant_id, cell_id, mode, purpose,
                         min_travel_time_minutes, nearest_destination_id,
                         departure_time)
                    VALUES
                        (:tenant_id, :cell_id, :mode, :purpose,
                         :min_tt, :dest_id, :departure_time)
                """),
                batch,
            )
    else:
        min_records = []

    # ── 5. Combined scores ──
    weights_rows = []
    for mode, purposes in config.combined_weights.items():
        for purpose, w in purposes.items():
            weights_rows.append({"mode": mode, "purpose": purpose, "w": w})
    weights_df = pd.DataFrame(weights_rows)

    merged = grouped.merge(weights_df, on=["mode", "purpose"], how="inner")
    merged["weighted"] = merged["score_normalized"] * merged["w"]

    combined = merged.groupby("cell_id")["weighted"].sum().reset_index()
    combined.columns = ["cell_id", "combined_score"]

    c_min, c_max = combined["combined_score"].min(), combined["combined_score"].max()
    if c_max == c_min:
        combined["combined_score_normalized"] = 0.0
    else:
        combined["combined_score_normalized"] = (
            (combined["combined_score"] - c_min) / (c_max - c_min) * 100.0
        )

    session.execute(
        text(
            "DELETE FROM combined_scores "
            "WHERE tenant_id = :tid AND departure_time = :dep_time"
        ),
        {"tid": tenant_id, "dep_time": departure_time},
    )

    weights_json = json.dumps(config.combined_weights)
    c_records = combined.to_dict("records")
    for i in range(0, len(c_records), BATCH_SIZE):
        batch = [
            {
                "tenant_id": tenant_id,
                "cell_id": int(r["cell_id"]),
                "combined_score": float(r["combined_score"]),
                "combined_score_normalized": float(r["combined_score_normalized"]),
                "weights": weights_json,
                "departure_time": departure_time,
            }
            for r in c_records[i : i + BATCH_SIZE]
        ]
        session.execute(
            text("""
                INSERT INTO combined_scores
                    (tenant_id, cell_id, combined_score,
                     combined_score_normalized, weights, departure_time)
                VALUES
                    (:tenant_id, :cell_id, :combined_score,
                     :combined_score_normalized, CAST(:weights AS jsonb),
                     :departure_time)
            """),
            batch,
        )

    log.info(
        "scoring_slot_complete",
        departure_time=departure_time,
        scores=len(records),
        combined=len(c_records),
        min_tt=len(min_records),
    )

    return {
        "scores_written": len(records),
        "combined_written": len(c_records),
        "min_travel_times_written": len(min_records),
    }
