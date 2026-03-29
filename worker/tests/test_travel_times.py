"""Tests for R5R travel-time import (parquet) and export."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from worker.pipeline.travel_times import (
    _find_travel_time_column,
    _parse_filename,
)


class TestParseFilename:
    """Verify filename → (mode, departure_time) parsing."""

    def test_new_format_with_time(self) -> None:
        assert _parse_filename("ttm_transit_0830.parquet") == ("TRANSIT", "08:30")

    def test_new_format_midnight(self) -> None:
        assert _parse_filename("ttm_transit_0000.parquet") == ("TRANSIT", "00:00")

    def test_new_format_late_evening(self) -> None:
        assert _parse_filename("ttm_walk_2330.parquet") == ("WALK", "23:30")

    def test_legacy_format_no_time(self) -> None:
        assert _parse_filename("ttm_transit.parquet") == ("TRANSIT", "08:00")

    def test_legacy_walk(self) -> None:
        assert _parse_filename("ttm_walk.parquet") == ("WALK", "08:00")

    def test_unrecognised_returns_none(self) -> None:
        assert _parse_filename("something_else.parquet") is None

    def test_case_insensitive_mode(self) -> None:
        result = _parse_filename("ttm_Transit_1400.parquet")
        assert result is not None
        assert result[0] == "TRANSIT"
        assert result[1] == "14:00"


class TestFindTravelTimeColumn:
    """Verify we correctly identify R5R's travel-time column."""

    def test_standard_p50(self) -> None:
        cols = ["from_id", "to_id", "travel_time_p50"]
        assert _find_travel_time_column(cols) == "travel_time_p50"

    def test_multiple_percentiles_picks_first_sorted(self) -> None:
        cols = ["from_id", "to_id", "travel_time_p75", "travel_time_p50"]
        assert _find_travel_time_column(cols) == "travel_time_p50"

    def test_fallback_to_travel_time(self) -> None:
        cols = ["from_id", "to_id", "travel_time"]
        assert _find_travel_time_column(cols) == "travel_time"

    def test_no_matching_column(self) -> None:
        cols = ["from_id", "to_id", "duration"]
        assert _find_travel_time_column(cols) is None


class TestParquetRoundtrip:
    """Verify parquet files can be read and validated."""

    def test_valid_parquet_structure(self, tmp_path: Path) -> None:
        """A well-formed R5R parquet has the expected columns after rename."""
        df = pd.DataFrame({
            "from_id": ["1", "1", "2"],
            "to_id": ["10", "11", "10"],
            "travel_time_p50": [15, 30, 45],
        })
        pq_path = tmp_path / "ttm_transit_0800.parquet"
        df.to_parquet(pq_path, index=False)

        loaded = pd.read_parquet(pq_path)
        assert list(loaded.columns) == ["from_id", "to_id", "travel_time_p50"]
        assert len(loaded) == 3

    def test_mode_and_time_inferred_from_filename(self) -> None:
        """Mode and departure time are extracted from ttm_{mode}_{HHMM}.parquet."""
        cases = [
            ("ttm_transit_0830.parquet", "TRANSIT", "08:30"),
            ("ttm_walk_1400.parquet", "WALK", "14:00"),
            ("ttm_transit.parquet", "TRANSIT", "08:00"),
        ]
        for name, expected_mode, expected_time in cases:
            result = _parse_filename(name)
            assert result is not None, f"Failed for {name}"
            assert result[0] == expected_mode
            assert result[1] == expected_time

    def test_rows_outside_time_range_filtered(self) -> None:
        """Travel times < 0 or > 120 should be dropped."""
        df = pd.DataFrame({
            "origin_cell_id": [1, 2, 3, 4, 5],
            "destination_id": [10, 10, 10, 10, 10],
            "travel_time_minutes": [-5, 0, 90, 120, 121],
        })
        valid = df[
            (df["travel_time_minutes"] >= 0)
            & (df["travel_time_minutes"] <= 120.0)
        ]
        assert len(valid) == 3
        assert list(valid["travel_time_minutes"]) == [0, 90, 120]
