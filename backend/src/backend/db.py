"""DuckDB-backed data layer.

Loads Parquet files (local or GCS) into an in-memory DuckDB database
and provides a thin session wrapper that mirrors the subset of the
SQLAlchemy interface used by our API routers.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Row / Result wrappers — keep API routers compatible with minimal changes
# ---------------------------------------------------------------------------


class DuckDBRow:
    """Row wrapper supporting both attribute and index access."""

    __slots__ = ("_cols", "_vals", "_map")

    def __init__(self, columns: list[str], values: tuple[Any, ...]) -> None:
        object.__setattr__(self, "_cols", columns)
        object.__setattr__(self, "_vals", values)
        object.__setattr__(self, "_map", dict(zip(columns, values)))

    # attribute access – row.name, row.geometry, …
    def __getattr__(self, name: str) -> Any:
        try:
            return self._map[name]
        except KeyError:
            raise AttributeError(name) from None

    # index access – row[0], row["name"]
    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._vals[key]
        return self._map[key]

    @property
    def _mapping(self) -> dict[str, Any]:
        return dict(self._map)


class DuckDBResult:
    """Mimics SQLAlchemy CursorResult for our read-only use case."""

    def __init__(self, cursor: duckdb.DuckDBPyConnection) -> None:
        self._cursor = cursor
        self._columns: list[str] = (
            [desc[0] for desc in cursor.description] if cursor.description else []
        )

    def fetchall(self) -> list[DuckDBRow]:
        return [DuckDBRow(self._columns, row) for row in self._cursor.fetchall()]

    def fetchone(self) -> DuckDBRow | None:
        row = self._cursor.fetchone()
        return DuckDBRow(self._columns, row) if row else None

    def one(self) -> DuckDBRow:
        row = self.fetchone()
        if row is None:
            raise LookupError("Expected exactly one row, got none")
        return row

    def one_or_none(self) -> DuckDBRow | None:
        return self.fetchone()

    def scalar(self) -> Any:
        row = self.fetchone()
        return row[0] if row else None

    def __iter__(self) -> Iterator[DuckDBRow]:
        return iter(self.fetchall())


class DuckDBSession:
    """Thread-safe session matching the interface our routers expect.

    DuckDB connections are not safe for concurrent access from multiple
    threads.  FastAPI may serve requests on different threads, so we
    serialise every query behind a lock.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection, lock: threading.Lock) -> None:
        self._conn = conn
        self._lock = lock

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> DuckDBResult:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params or {})
            return DuckDBResult(cur)

    def has_table(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        with self._lock:
            try:
                cur = self._conn.cursor()
                cur.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_name = $1",
                    [table_name],
                )
                return cur.fetchone()[0] > 0
            except duckdb.CatalogException:
                return False
            except duckdb.Error:
                logger.warning("has_table(%s) failed unexpectedly", table_name, exc_info=True)
                return False


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_conn: duckdb.DuckDBPyConnection | None = None
_conn_lock = threading.Lock()

# Tables that contain geometry columns (stored as WKB in Parquet).
_GEO_TABLES: dict[str, list[str]] = {
    "grid_cells": ["geom", "centroid"],
    "boundaries": ["geom"],
    "municipalities": ["geom"],
    "comarcas": ["geom"],
    "nucleos": ["geom"],
    "destinations": ["geom"],
    "gtfs_stops": ["geom"],
    "gtfs_routes": ["geom"],
    "stop_frequency": ["geom"],
}

# All serving tables expected in the data dir.
_ALL_TABLES = [
    "grid_cells",
    "boundaries",
    "municipalities",
    "comarcas",
    "nucleos",
    "destinations",
    "destination_types",
    "connectivity_scores",
    "combined_scores",
    "min_travel_times",
    "gtfs_stops",
    "gtfs_routes",
    "stop_frequency",
    "municipality_demographics",
    "municipality_income",
    "municipality_car_ownership",
    "tenants",
    "modes",
]


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def _download_gcs(bucket: str, prefix: str, dest: Path) -> None:
    """Download Parquet files from GCS to a local directory."""
    from google.cloud import storage as gcs  # lazy import

    client = gcs.Client()
    blobs = client.list_blobs(bucket, prefix=prefix)
    for blob in blobs:
        if not blob.name.endswith(".parquet"):
            continue
        local_path = dest / Path(blob.name).name
        logger.info("Downloading gs://%s/%s → %s", bucket, blob.name, local_path)
        blob.download_to_filename(str(local_path))


def _resolve_data_dir(settings: Settings) -> Path:
    """Return a local directory containing the Parquet files."""
    if settings.data_source == "gcs":
        tmp = Path(tempfile.mkdtemp(prefix="bizkaia_"))
        _download_gcs(settings.gcs_bucket, settings.gcs_prefix, tmp)
        return tmp
    return Path(settings.data_dir)


def _load_table(conn: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    """Load a single Parquet file into DuckDB, converting WKB geometry."""
    if not path.exists():
        logger.warning("Skipping %s – file not found: %s", table, path)
        return

    conn.execute(
        f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{path}')"
    )

    # Normalise geometry column name: GeoParquet uses 'geometry' but our
    # SQL layer expects 'geom' everywhere.
    try:
        conn.execute(f"ALTER TABLE {table} RENAME COLUMN geometry TO geom")
    except duckdb.Error:
        pass  # Column doesn't exist or already named geom

    # Ensure every table has an 'id' column (some Parquet files omit it).
    try:
        conn.execute(f"SELECT id FROM {table} LIMIT 0")
    except duckdb.Error:
        conn.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT ROW_NUMBER() OVER () AS id, * FROM {table}"
        )

    # Convert WKB blobs → native GEOMETRY for spatial queries
    geo_cols = _GEO_TABLES.get(table, [])
    for col in geo_cols:
        try:
            conn.execute(f"""
                CREATE OR REPLACE TABLE {table} AS
                SELECT * EXCLUDE ({col}),
                       ST_GeomFromWKB({col}) AS {col}
                FROM {table}
            """)
        except duckdb.Error:
            # Column might already be GEOMETRY, or not present at all
            logger.debug("Geometry conversion skipped for %s.%s", table, col)


def init_db(settings: Settings | None = None) -> None:
    """Initialise an in-memory DuckDB database from Parquet files.

    Call once at application startup.  The data fits comfortably in RAM
    (<100 MB for Bizkaia) so there is no need for a file-based DB.
    """
    global _conn

    if settings is None:
        settings = get_settings()

    data_dir = _resolve_data_dir(settings)

    logger.info("Initialising DuckDB (in-memory) from %s", data_dir)

    _conn = duckdb.connect()  # in-memory
    _conn.install_extension("spatial")
    _conn.load_extension("spatial")

    for table in _ALL_TABLES:
        _load_table(_conn, table, data_dir / f"{table}.parquet")

    # Add centroid column to grid_cells (derived from geom)
    try:
        _conn.execute("""
            ALTER TABLE grid_cells ADD COLUMN centroid GEOMETRY;
            UPDATE grid_cells SET centroid = ST_Centroid(geom);
        """)
    except duckdb.Error:
        pass  # Table might not exist or centroid already present

    logger.info("DuckDB initialised – %d tables loaded", len(_ALL_TABLES))


def reload_db() -> None:
    """Re-read Parquet files (e.g. after a worker data refresh)."""
    init_db()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db() -> Iterator[DuckDBSession]:
    """FastAPI dependency – yields a DuckDBSession per request."""
    if _conn is None:
        raise RuntimeError("Database not initialised – call init_db() first")
    yield DuckDBSession(_conn, _conn_lock)
