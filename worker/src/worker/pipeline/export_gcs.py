"""Upload serving Parquet files to Google Cloud Storage."""

from __future__ import annotations

from pathlib import Path

import structlog

logger = structlog.get_logger()

SERVING_FILES = [
    "grid_cells.parquet",
    "boundaries.parquet",
    "municipalities.parquet",
    "comarcas.parquet",
    "nucleos.parquet",
    "destinations.parquet",
    "destination_types.parquet",
    "connectivity_scores.parquet",
    "combined_scores.parquet",
    "min_travel_times.parquet",
    "gtfs_stops.parquet",
    "gtfs_routes.parquet",
    "stop_frequency.parquet",
    "municipality_demographics.parquet",
    "municipality_income.parquet",
    "municipality_car_ownership.parquet",
    "tenants.parquet",
    "modes.parquet",
]


def upload_serving_to_gcs(
    serving_dir: str | Path,
    bucket_name: str,
    prefix: str = "serving",
) -> dict[str, str]:
    """Upload all serving Parquet files to a GCS bucket.

    Returns a dict of filename -> status ("uploaded" or "skipped").
    """
    from google.cloud import storage as gcs

    serving = Path(serving_dir)
    client = gcs.Client()
    bucket = client.bucket(bucket_name)

    results: dict[str, str] = {}

    for filename in SERVING_FILES:
        local_path = serving / filename
        if not local_path.exists():
            results[filename] = "skipped (not found)"
            continue

        blob_name = f"{prefix}/{filename}" if prefix else filename
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_path))

        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info(
            "gcs_uploaded",
            file=filename,
            blob=blob_name,
            size_mb=round(size_mb, 2),
        )
        results[filename] = f"uploaded ({size_mb:.1f} MB)"

    return results
