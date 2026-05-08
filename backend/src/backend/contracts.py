"""Schema contracts for the Parquet tables loaded into DuckDB.

The worker writes Parquet to ``data/serving/`` and the backend reads it back
into DuckDB at startup. Without an explicit contract, a column rename in the
worker silently breaks API endpoints at request time. This module asserts the
contract at load time so a schema mismatch fails the deploy / hot-reload
loudly instead of poisoning user-facing requests.

Validation uses DuckDB's own ``DESCRIBE`` (cheap; no data is read) so we
don't pull in pyarrow/pandas just to check column names.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import structlog

logger = structlog.stdlib.get_logger(__name__)


class SchemaContractError(RuntimeError):
    """Raised when a loaded Parquet table is missing required columns."""


# Column types are matched loosely against DuckDB's textual type names.
# Each entry is a set of acceptable type prefixes (case-insensitive) so we
# don't break on numeric width changes (e.g. INTEGER vs BIGINT).
_NUMERIC = {"BIGINT", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "SMALLINT", "TINYINT"}
_STRING = {"VARCHAR", "TEXT", "STRING"}
_GEOMETRY = {"BLOB", "GEOMETRY", "VARCHAR"}  # WKB before conversion, GEOMETRY after


@dataclass(frozen=True)
class ColumnContract:
    name: str
    type_alternatives: frozenset[str]
    required: bool = True


@dataclass(frozen=True)
class TableContract:
    table: str
    columns: tuple[ColumnContract, ...]


# Tables critical to API correctness. Optional tables (demographics, income,
# etc.) are intentionally not contracted yet — they're queried defensively
# with COALESCE/LEFT JOIN, so missing columns degrade gracefully.
_CRITICAL_CONTRACTS: tuple[TableContract, ...] = (
    TableContract(
        table="grid_cells",
        columns=(
            ColumnContract("cell_code", frozenset(_STRING)),
            ColumnContract("population", frozenset(_NUMERIC)),
            ColumnContract("tenant_id", frozenset(_STRING)),
            ColumnContract("geometry", frozenset(_GEOMETRY)),
        ),
    ),
    TableContract(
        table="connectivity_scores",
        columns=(
            ColumnContract("cell_id", frozenset(_NUMERIC)),
            ColumnContract("tenant_id", frozenset(_STRING)),
            ColumnContract("mode", frozenset(_STRING)),
            ColumnContract("purpose", frozenset(_STRING)),
            ColumnContract("departure_time", frozenset(_STRING)),
            ColumnContract("score_normalized", frozenset(_NUMERIC)),
        ),
    ),
    TableContract(
        table="combined_scores",
        columns=(
            ColumnContract("cell_id", frozenset(_NUMERIC)),
            ColumnContract("tenant_id", frozenset(_STRING)),
            ColumnContract("departure_time", frozenset(_STRING)),
            ColumnContract("combined_score_normalized", frozenset(_NUMERIC)),
        ),
    ),
    TableContract(
        table="min_travel_times",
        columns=(
            ColumnContract("cell_id", frozenset(_NUMERIC)),
            ColumnContract("tenant_id", frozenset(_STRING)),
            ColumnContract("mode", frozenset(_STRING)),
            ColumnContract("purpose", frozenset(_STRING)),
            ColumnContract("departure_time", frozenset(_STRING)),
            ColumnContract("min_travel_time_minutes", frozenset(_NUMERIC)),
        ),
    ),
)

CONTRACTS: dict[str, TableContract] = {c.table: c for c in _CRITICAL_CONTRACTS}


def _describe_table(conn: duckdb.DuckDBPyConnection, table: str) -> dict[str, str]:
    """Return ``{column_name: duckdb_type_name}`` for a loaded table."""
    rows = conn.execute(f"DESCRIBE {table}").fetchall()
    # DuckDB DESCRIBE returns (column_name, column_type, null, key, default, extra).
    return {row[0]: row[1] for row in rows}


def _type_matches(actual: str, alternatives: frozenset[str]) -> bool:
    """Loose match: actual type starts with any acceptable prefix."""
    actual_upper = actual.upper().split("(")[0].strip()
    return any(actual_upper.startswith(alt.upper()) for alt in alternatives)


def validate_loaded_table(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Validate a freshly loaded table against its contract.

    Returns a list of human-readable issue strings. The caller decides
    whether to log+continue or raise.
    """
    contract = CONTRACTS.get(table)
    if contract is None:
        return []

    actual = _describe_table(conn, table)
    issues: list[str] = []

    for col in contract.columns:
        if col.name not in actual:
            if col.required:
                issues.append(f"missing required column '{col.name}'")
            continue
        if not _type_matches(actual[col.name], col.type_alternatives):
            issues.append(
                f"column '{col.name}' has type {actual[col.name]!r}, "
                f"expected one of {sorted(col.type_alternatives)}"
            )

    return issues


def assert_loaded_table(conn: duckdb.DuckDBPyConnection, table: str) -> None:
    """Validate and raise on any issue. Use during init_db to fail fast."""
    issues = validate_loaded_table(conn, table)
    if not issues:
        return
    logger.error("contract.violation", table=table, issues=issues)
    raise SchemaContractError(
        f"Schema contract violated for table {table!r}: {'; '.join(issues)}"
    )
