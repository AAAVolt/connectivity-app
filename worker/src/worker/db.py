"""Transient DuckDB query engine for the worker pipeline.

Used during scoring and aggregation steps to query across Parquet files.
Not a persistent database — created fresh each pipeline run.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import structlog

logger = structlog.get_logger()


def create_engine() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB connection with the spatial extension."""
    conn = duckdb.connect()
    conn.install_extension("spatial")
    conn.load_extension("spatial")
    return conn


def register_parquet(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    path: str | Path,
) -> None:
    """Register a Parquet file (or directory of files) as a DuckDB table."""
    p = Path(path)
    if not p.exists():
        logger.warning("parquet_not_found", table=table_name, path=str(p))
        return
    if p.is_dir():
        conn.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS "
            f"SELECT * FROM read_parquet('{p}/*.parquet')"
        )
    else:
        conn.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS "
            f"SELECT * FROM read_parquet('{p}')"
        )
    logger.debug("parquet_registered", table=table_name, path=str(p))


def load_serving_tables(
    conn: duckdb.DuckDBPyConnection,
    serving_dir: str | Path,
) -> None:
    """Load all serving Parquet files into DuckDB for cross-table queries."""
    d = Path(serving_dir)
    tables = [
        "grid_cells", "boundaries", "municipalities", "comarcas", "nucleos",
        "destinations", "destination_types", "modes", "tenants",
        "connectivity_scores", "combined_scores", "min_travel_times",
        "gtfs_stops", "gtfs_routes", "stop_frequency",
        "municipality_demographics", "municipality_income",
        "municipality_car_ownership",
    ]
    for table in tables:
        path = d / f"{table}.parquet"
        if path.exists():
            register_parquet(conn, table, path)
