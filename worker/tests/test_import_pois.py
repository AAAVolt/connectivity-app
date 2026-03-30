"""Tests for the POI CSV import pipeline."""

from pathlib import Path

import pytest

from worker.pipeline.import_pois import _validate_row


class TestValidateRow:
    """Unit tests for row validation (no DB required)."""

    def test_valid_row(self) -> None:
        row = {"name": "Hospital", "lon": "-2.95", "lat": "43.26", "weight": "2.0"}
        result = _validate_row(row, 2, "health.csv")
        assert result == ("Hospital", -2.95, 43.26, 2.0)

    def test_default_weight(self) -> None:
        row = {"name": "School A", "lon": "-2.90", "lat": "43.25", "weight": ""}
        result = _validate_row(row, 2, "schools.csv")
        assert result is not None
        assert result[3] == 1.0

    def test_missing_weight_column(self) -> None:
        row = {"name": "School A", "lon": "-2.90", "lat": "43.25"}
        result = _validate_row(row, 2, "schools.csv")
        assert result is not None
        assert result[3] == 1.0

    def test_missing_name(self) -> None:
        row = {"name": "", "lon": "-2.90", "lat": "43.25"}
        result = _validate_row(row, 2, "test.csv")
        assert result is None

    def test_invalid_lon(self) -> None:
        row = {"name": "Place", "lon": "abc", "lat": "43.25"}
        result = _validate_row(row, 2, "test.csv")
        assert result is None

    def test_invalid_lat(self) -> None:
        row = {"name": "Place", "lon": "-2.90", "lat": "not_a_number"}
        result = _validate_row(row, 2, "test.csv")
        assert result is None

    def test_coords_outside_bizkaia(self) -> None:
        row = {"name": "Madrid", "lon": "-3.70", "lat": "40.42"}
        result = _validate_row(row, 2, "test.csv")
        assert result is None

    def test_negative_weight(self) -> None:
        row = {"name": "Place", "lon": "-2.90", "lat": "43.25", "weight": "-1"}
        result = _validate_row(row, 2, "test.csv")
        assert result is None

    def test_zero_weight(self) -> None:
        row = {"name": "Place", "lon": "-2.90", "lat": "43.25", "weight": "0"}
        result = _validate_row(row, 2, "test.csv")
        assert result is None

    def test_non_numeric_weight(self) -> None:
        row = {"name": "Place", "lon": "-2.90", "lat": "43.25", "weight": "high"}
        result = _validate_row(row, 2, "test.csv")
        assert result is None

    def test_boundary_coords_valid(self) -> None:
        """Coords at the edge of the Bizkaia bounding box should be accepted."""
        row = {"name": "Edge", "lon": "-3.5", "lat": "42.9"}
        result = _validate_row(row, 2, "test.csv")
        assert result is not None

    def test_whitespace_handling(self) -> None:
        row = {"name": "  Hospital  ", "lon": " -2.95 ", "lat": " 43.26 ", "weight": " 1.5 "}
        result = _validate_row(row, 2, "test.csv")
        assert result == ("Hospital", -2.95, 43.26, 1.5)


class TestImportPoisFromCsv:
    """Tests for the full import function (requires tmp CSV files, no DB)."""

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError if pois_dir doesn't exist."""
        from unittest.mock import MagicMock

        from worker.pipeline.import_pois import import_pois_from_csv

        session = MagicMock()
        with pytest.raises(FileNotFoundError):
            import_pois_from_csv(session, "fake-tenant", tmp_path / "nope")

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        """No CSV files → empty dict, no DB calls."""
        from unittest.mock import MagicMock

        from worker.pipeline.import_pois import import_pois_from_csv

        session = MagicMock()
        result = import_pois_from_csv(session, "fake-tenant", tmp_path)
        assert result == {}
        session.execute.assert_not_called()

    def test_csv_missing_required_columns_skipped(self, tmp_path: Path) -> None:
        """CSV without required columns is skipped."""
        from unittest.mock import MagicMock

        from worker.pipeline.import_pois import import_pois_from_csv

        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("foo,bar\n1,2\n")

        session = MagicMock()
        # _ensure_destination_type will be called, mock it
        session.execute.return_value.scalar_one_or_none.return_value = 1
        result = import_pois_from_csv(session, "fake-tenant", tmp_path)
        # The file is skipped so no destinations imported
        assert result == {}
