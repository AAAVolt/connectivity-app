"""Compute connectivity and combined scores for all grid cells."""

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

    Pipeline per departure_time slot:
      1. Fetch travel times joined with destination types.
      2. Map destination types to purpose buckets.
      3. Apply impedance per (mode, purpose).
      4. Aggregate per (cell, mode, purpose).
      5. Apply diminishing returns (concave transform).
      6. Normalize per (mode, purpose) to [0, 100].
      7. Write connectivity_scores.
      8. Compute and write min travel times.
      9. Compute combined scores (weighted average of normalized).
      10. Normalize combined to [0, 100].
      11. Write combined_scores.
    """
    if config is None:
        config = load_scoring_config()

    log = logger.bind(tenant_id=tenant_id)
    log.info("scoring_start")

    # Discover departure_time slots to process
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
            # Fallback for legacy data without departure_time
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
    """Compute scores for a single departure_time slot."""

    # ── 1. Fetch travel times with destination type info ──
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
        """),
        {"tid": tenant_id, "dep_time": departure_time, "max_tt": config.max_travel_time},
    ).fetchall()

    if not rows:
        log.warning("no_travel_times_found", departure_time=departure_time)
        return {"scores_written": 0, "combined_written": 0, "min_travel_times_written": 0}

    df = pd.DataFrame(
        rows, columns=["cell_id", "mode", "dest_type", "travel_time", "weight"]
    )

    # ── 1b. Fetch destination IDs for min travel time tracking ──
    rows_with_dest = session.execute(
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
        """),
        {"tid": tenant_id, "dep_time": departure_time, "max_tt": config.max_travel_time},
    ).fetchall()

    df_full = pd.DataFrame(
        rows_with_dest,
        columns=["cell_id", "mode", "dest_type", "travel_time", "destination_id"],
    )

    # ── 2. Map destination type → purpose bucket ──
    df["purpose"] = df["dest_type"].map(config.purpose_map)
    df = df.dropna(subset=["purpose"])
    df_full["purpose"] = df_full["dest_type"].map(config.purpose_map)
    df_full = df_full.dropna(subset=["purpose"])

    if df.empty:
        log.warning("no_mapped_purposes", departure_time=departure_time)
        return {"scores_written": 0, "combined_written": 0, "min_travel_times_written": 0}

    # ── 3. Apply impedance ──
    def _contribution(row: pd.Series) -> float:
        alpha = config.impedance.get(row["mode"], {}).get(row["purpose"], 0.05)
        return float(row["weight"]) * exponential_impedance(
            float(row["travel_time"]), alpha
        )

    df["contribution"] = df.apply(_contribution, axis=1)

    # ── 4. Aggregate per (cell, mode, purpose) ──
    grouped = (
        df.groupby(["cell_id", "mode", "purpose"])["contribution"]
        .sum()
        .reset_index()
        .rename(columns={"contribution": "raw_score"})
    )

    # ── 5. Diminishing returns ──
    grouped["score"] = grouped["raw_score"].apply(
        lambda x: concave_transform(x, config.beta)
    )

    # ── 6. Normalize per (mode, purpose) to [0, 100] ──
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

    # ── 7. Write connectivity_scores ──
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

    # ── 7b. Compute and write min travel times ──
    min_tt = (
        df_full.loc[
            df_full.groupby(["cell_id", "mode", "purpose"])["travel_time"].idxmin()
        ][["cell_id", "mode", "purpose", "travel_time", "destination_id"]]
        .reset_index(drop=True)
    )

    session.execute(
        text(
            "DELETE FROM min_travel_times "
            "WHERE tenant_id = :tid AND departure_time = :dep_time"
        ),
        {"tid": tenant_id, "dep_time": departure_time},
    )

    min_records = min_tt.to_dict("records")
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

    # ── 8. Combined scores ──
    weights_rows = []
    for mode, purposes in config.combined_weights.items():
        for purpose, w in purposes.items():
            weights_rows.append({"mode": mode, "purpose": purpose, "w": w})
    weights_df = pd.DataFrame(weights_rows)

    merged = grouped.merge(weights_df, on=["mode", "purpose"], how="inner")
    merged["weighted"] = merged["score_normalized"] * merged["w"]

    combined = merged.groupby("cell_id")["weighted"].sum().reset_index()
    combined.columns = ["cell_id", "combined_score"]

    # ── 9. Normalize combined to [0, 100] ──
    c_min, c_max = combined["combined_score"].min(), combined["combined_score"].max()
    if c_max == c_min:
        combined["combined_score_normalized"] = 0.0
    else:
        combined["combined_score_normalized"] = (
            (combined["combined_score"] - c_min) / (c_max - c_min) * 100.0
        )

    # ── 10. Write combined_scores ──
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
