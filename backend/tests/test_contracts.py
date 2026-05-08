"""Tests for the Parquet schema contract."""

from __future__ import annotations

import duckdb
import pytest

from backend.contracts import (
    SchemaContractError,
    assert_loaded_table,
    validate_loaded_table,
)


def _seed_grid_cells(conn: duckdb.DuckDBPyConnection, **overrides: str) -> None:
    """Build a grid_cells table from a SELECT, with column types as strings.

    overrides keys are column names; values are SQL expressions that produce
    the desired type (e.g. CAST(NULL AS BLOB) for geometry).
    """
    cols = {
        "id": "1::INTEGER",
        "cell_code": "'E430000_N4790000'::VARCHAR",
        "population": "150.0::DOUBLE",
        "tenant_id": "'00000000-0000-0000-0000-000000000001'::VARCHAR",
        "geometry": "CAST(NULL AS BLOB)",
    }
    cols.update(overrides)
    select = ", ".join(f"{expr} AS {name}" for name, expr in cols.items())
    conn.execute(f"CREATE OR REPLACE TABLE grid_cells AS SELECT {select}")


def test_contract_passes_on_valid_grid_cells() -> None:
    conn = duckdb.connect()
    _seed_grid_cells(conn)
    assert validate_loaded_table(conn, "grid_cells") == []
    assert_loaded_table(conn, "grid_cells")  # does not raise


def test_contract_fails_when_required_column_missing() -> None:
    conn = duckdb.connect()
    # Build a grid_cells without 'population' to simulate a worker drift.
    conn.execute("""
        CREATE OR REPLACE TABLE grid_cells AS
        SELECT 1::INTEGER AS id,
               'E430000_N4790000'::VARCHAR AS cell_code,
               '00000000-0000-0000-0000-000000000001'::VARCHAR AS tenant_id,
               CAST(NULL AS BLOB) AS geometry
    """)
    issues = validate_loaded_table(conn, "grid_cells")
    assert any("population" in issue for issue in issues), issues

    with pytest.raises(SchemaContractError, match="population"):
        assert_loaded_table(conn, "grid_cells")


def test_contract_fails_on_wrong_column_type() -> None:
    conn = duckdb.connect()
    # tenant_id should be a string but here it's an integer.
    _seed_grid_cells(conn, tenant_id="42::INTEGER")
    issues = validate_loaded_table(conn, "grid_cells")
    assert any("tenant_id" in issue for issue in issues), issues


def test_unknown_table_returns_no_issues() -> None:
    """Tables without a contract are intentionally skipped, not failed."""
    conn = duckdb.connect()
    conn.execute("CREATE OR REPLACE TABLE made_up AS SELECT 1 AS x")
    assert validate_loaded_table(conn, "made_up") == []
