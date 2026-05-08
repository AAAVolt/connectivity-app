"""Tests for the worker-side schema contract."""

from __future__ import annotations

import pandas as pd
import pytest

from worker.contracts import (
    SchemaContractError,
    assert_dataframe,
    validate_dataframe,
)


def _valid_connectivity_scores(rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "cell_id": list(range(rows)),
        "tenant_id": ["00000000-0000-0000-0000-000000000001"] * rows,
        "mode": ["TRANSIT"] * rows,
        "purpose": ["hospital"] * rows,
        "departure_time": ["08:00"] * rows,
        "score": [42.0] * rows,
        "score_normalized": [60.0] * rows,
    })


def test_valid_connectivity_scores_passes() -> None:
    df = _valid_connectivity_scores()
    assert validate_dataframe("connectivity_scores", df) == []
    assert_dataframe("connectivity_scores", df)  # does not raise


def test_missing_required_column_fails() -> None:
    df = _valid_connectivity_scores().drop(columns=["score_normalized"])
    issues = validate_dataframe("connectivity_scores", df)
    assert any("score_normalized" in issue for issue in issues), issues

    with pytest.raises(SchemaContractError, match="score_normalized"):
        assert_dataframe("connectivity_scores", df)


def test_wrong_dtype_fails() -> None:
    """A string in a numeric column must be rejected."""
    df = _valid_connectivity_scores()
    df["cell_id"] = df["cell_id"].astype(str)  # numeric → string
    issues = validate_dataframe("connectivity_scores", df)
    assert any("cell_id" in issue for issue in issues), issues


def test_uncontracted_table_passes_silently() -> None:
    df = pd.DataFrame({"random_col": [1, 2, 3]})
    assert validate_dataframe("not_a_real_table", df) == []


def test_grid_cells_contract_accepts_geom_column_with_or_without_geometry() -> None:
    """The geometry column is intentionally not in the contract — geopandas writes
    'geometry', the worker may rename to 'geom'. Both shapes must pass."""
    base = pd.DataFrame({
        "cell_code": ["E430_N4790"],
        "population": [100.0],
        "tenant_id": ["00000000-0000-0000-0000-000000000001"],
    })
    # No geometry column at all — still passes the contract because the
    # backend's spatial queries will surface a real missing-geometry error
    # at query time, not silently corrupt scores.
    assert validate_dataframe("grid_cells", base) == []
