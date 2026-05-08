"""Worker-side schema contracts for serving Parquet tables.

Mirrors ``backend/src/backend/contracts.py`` so a column drift is caught at
**write time** in the worker, not later when the backend tries to load the
file. The backend contract validates loaded DuckDB tables; this one
validates pandas / geopandas DataFrames before they're written to disk.

Keep the column lists in sync with the backend module. Both modules live in
separate Python packages today, so we duplicate the definitions and rely on
test coverage to keep them aligned. (A future refactor could lift them into
a shared package.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import pandas as pd

logger = structlog.get_logger()


class SchemaContractError(RuntimeError):
    """Raised when a DataFrame doesn't satisfy its serving-table contract."""


# Loose dtype kinds — match the backend's loose type matching. We don't
# care about width (int32 vs int64), only kind.
_NUMERIC_KINDS = frozenset({"i", "u", "f"})            # int / uint / float
_STRING_KINDS = frozenset({"O", "U"})                  # object / unicode
_TIME_KINDS = frozenset({"O", "M"})                    # datetime / iso strings
# Geometry presence is verified by downstream spatial SQL — an absent
# geometry column crashes the backend's spatial queries loudly — so we
# don't contract on it (column name varies: 'geometry' from geopandas,
# 'geom' after rename_geometry, and the dtype kind is just 'O').


@dataclass(frozen=True)
class ColumnContract:
    name: str
    kinds: frozenset[str]
    required: bool = True


@dataclass(frozen=True)
class TableContract:
    table: str
    columns: tuple[ColumnContract, ...]


_CONTRACTS: tuple[TableContract, ...] = (
    TableContract(
        table="grid_cells",
        columns=(
            ColumnContract("cell_code", _STRING_KINDS),
            ColumnContract("population", _NUMERIC_KINDS),
            ColumnContract("tenant_id", _STRING_KINDS),
        ),
    ),
    TableContract(
        table="connectivity_scores",
        columns=(
            ColumnContract("cell_id", _NUMERIC_KINDS),
            ColumnContract("tenant_id", _STRING_KINDS),
            ColumnContract("mode", _STRING_KINDS),
            ColumnContract("purpose", _STRING_KINDS),
            ColumnContract("departure_time", _STRING_KINDS),
            ColumnContract("score_normalized", _NUMERIC_KINDS),
        ),
    ),
    TableContract(
        table="combined_scores",
        columns=(
            ColumnContract("cell_id", _NUMERIC_KINDS),
            ColumnContract("tenant_id", _STRING_KINDS),
            ColumnContract("departure_time", _STRING_KINDS),
            ColumnContract("combined_score_normalized", _NUMERIC_KINDS),
        ),
    ),
    TableContract(
        table="min_travel_times",
        columns=(
            ColumnContract("cell_id", _NUMERIC_KINDS),
            ColumnContract("tenant_id", _STRING_KINDS),
            ColumnContract("mode", _STRING_KINDS),
            ColumnContract("purpose", _STRING_KINDS),
            ColumnContract("departure_time", _STRING_KINDS),
            ColumnContract("min_travel_time_minutes", _NUMERIC_KINDS),
        ),
    ),
)

CONTRACTS: dict[str, TableContract] = {c.table: c for c in _CONTRACTS}


def _column_kind(series: "pd.Series") -> str:
    """Return numpy kind char for a pandas Series.

    Special-cases geopandas GeoSeries (which has dtype 'geometry' that maps
    to kind 'O' in numpy but is semantically distinct).
    """
    return series.dtype.kind


def validate_dataframe(table: str, df: "pd.DataFrame") -> list[str]:
    """Return a list of human-readable issues. Empty list = valid."""
    contract = CONTRACTS.get(table)
    if contract is None:
        return []  # uncontracted tables pass silently

    issues: list[str] = []
    for col in contract.columns:
        if col.name not in df.columns:
            if col.required:
                issues.append(f"missing required column '{col.name}'")
            continue
        kind = _column_kind(df[col.name])
        if kind not in col.kinds:
            issues.append(
                f"column '{col.name}' has dtype kind {kind!r}, "
                f"expected one of {sorted(col.kinds)}"
            )
    return issues


def assert_dataframe(table: str, df: "pd.DataFrame") -> None:
    """Validate and raise on any contract violation. Use before writing."""
    issues = validate_dataframe(table, df)
    if not issues:
        return
    logger.error(
        "contract.violation",
        table=table,
        issues=issues,
        rows=len(df),
        columns=list(df.columns),
    )
    raise SchemaContractError(
        f"Schema contract violated for table {table!r}: {'; '.join(issues)}"
    )
