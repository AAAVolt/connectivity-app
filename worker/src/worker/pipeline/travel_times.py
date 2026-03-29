"""Import travel time CSV files produced by the R5R routing container."""

from __future__ import annotations

import csv
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

ALLOWED_MODES = frozenset({"WALK", "TRANSIT"})
MAX_TRAVEL_TIME = 60.0
BATCH_SIZE = 5000


def import_travel_times(
    session: Session,
    tenant_id: str,
    input_dir: Path,
) -> dict[str, object]:
    """Import travel time CSVs into the travel_times table.

    Expected CSV columns:
        tenant_id, origin_id, dest_id, mode, time_period, travel_time_min

    Rows are filtered by tenant_id and validated:
      - mode must be in ALLOWED_MODES
      - travel_time_min must be in [0, MAX_TRAVEL_TIME]

    Uses upsert (ON CONFLICT DO UPDATE) for idempotent re-imports.

    Returns statistics dict.
    """
    log = logger.bind(tenant_id=tenant_id, input_dir=str(input_dir))
    log.info("travel_time_import_start")

    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {input_dir}")

    total_imported = 0
    total_skipped = 0
    min_time = float("inf")
    max_time = float("-inf")

    for csv_file in csv_files:
        log.info("processing_file", file=csv_file.name)
        batch: list[dict[str, object]] = []

        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["tenant_id"] != tenant_id:
                    continue

                mode = row["mode"].strip().upper()
                try:
                    travel_time = float(row["travel_time_min"])
                except (ValueError, KeyError):
                    total_skipped += 1
                    continue

                if mode not in ALLOWED_MODES:
                    total_skipped += 1
                    continue
                if travel_time < 0 or travel_time > MAX_TRAVEL_TIME:
                    total_skipped += 1
                    continue

                batch.append(
                    {
                        "tenant_id": tenant_id,
                        "origin_cell_id": int(row["origin_id"]),
                        "destination_id": int(row["dest_id"]),
                        "mode": mode,
                        "travel_time_minutes": travel_time,
                    }
                )

                min_time = min(min_time, travel_time)
                max_time = max(max_time, travel_time)

                if len(batch) >= BATCH_SIZE:
                    _upsert_batch(session, batch)
                    total_imported += len(batch)
                    batch = []

        if batch:
            _upsert_batch(session, batch)
            total_imported += len(batch)

    session.commit()

    stats: dict[str, object] = {
        "files_processed": len(csv_files),
        "rows_imported": total_imported,
        "rows_skipped": total_skipped,
        "min_travel_time": min_time if total_imported > 0 else 0.0,
        "max_travel_time": max_time if total_imported > 0 else 0.0,
    }
    log.info("travel_time_import_complete", **stats)
    return stats


def _upsert_batch(session: Session, batch: list[dict[str, object]]) -> None:
    """Upsert a batch of travel time records."""
    session.execute(
        text("""
            INSERT INTO travel_times
                (tenant_id, origin_cell_id, destination_id, mode, travel_time_minutes)
            VALUES
                (:tenant_id, :origin_cell_id, :destination_id, :mode, :travel_time_minutes)
            ON CONFLICT (tenant_id, origin_cell_id, destination_id, mode)
            DO UPDATE SET travel_time_minutes = EXCLUDED.travel_time_minutes
        """),
        batch,
    )
