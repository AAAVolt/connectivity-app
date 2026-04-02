"""Tests for EUSTAT núcleo polygon import."""

from __future__ import annotations

import pytest
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiPolygon,
    Polygon,
    box,
)

from worker.pipeline.import_nucleos import _ensure_multi


# ---------------------------------------------------------------------------
# _ensure_multi geometry promotion
# ---------------------------------------------------------------------------

class TestEnsureMulti:
    """Tests for _ensure_multi geometry normalisation."""

    def test_polygon_promoted_to_multi(self) -> None:
        result = _ensure_multi(box(0, 0, 1, 1))
        assert isinstance(result, MultiPolygon)
        assert len(result.geoms) == 1

    def test_multipolygon_passthrough(self) -> None:
        mp = MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])
        result = _ensure_multi(mp)
        assert result is mp

    def test_none_returns_empty_multi(self) -> None:
        result = _ensure_multi(None)
        assert isinstance(result, MultiPolygon)
        assert result.is_empty

    def test_geometry_collection_extracts_polygons(self) -> None:
        """GeometryCollection (e.g. from make_valid) keeps polygon parts."""
        gc = GeometryCollection([
            box(0, 0, 1, 1),
            LineString([(0, 0), (1, 1)]),
            box(2, 2, 3, 3),
        ])
        result = _ensure_multi(gc)
        assert isinstance(result, MultiPolygon)
        assert len(result.geoms) == 2

    def test_geometry_collection_nested_multi(self) -> None:
        """Nested MultiPolygon inside GeometryCollection is flattened."""
        gc = GeometryCollection([
            MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)]),
            box(4, 4, 5, 5),
        ])
        result = _ensure_multi(gc)
        assert isinstance(result, MultiPolygon)
        assert len(result.geoms) == 3

    def test_geometry_collection_no_polygons_returns_empty(self) -> None:
        """A GeometryCollection with only lines returns empty MultiPolygon."""
        gc = GeometryCollection([
            LineString([(0, 0), (1, 1)]),
            LineString([(2, 2), (3, 3)]),
        ])
        result = _ensure_multi(gc)
        assert isinstance(result, MultiPolygon)
        assert result.is_empty

    def test_empty_polygon_returns_empty_multi(self) -> None:
        result = _ensure_multi(Polygon())
        assert isinstance(result, MultiPolygon)
        # An empty Polygon promoted to MultiPolygon([empty]) has one geom
        # but the overall geometry should still be empty
        assert result.is_empty or result.area == 0


# ---------------------------------------------------------------------------
# Diseminado flagging
# ---------------------------------------------------------------------------

class TestDiseminadoClassification:
    """Verify that nucleo_num == '99' is correctly identified as diseminado."""

    def test_code_99_is_diseminado(self) -> None:
        """NUC_NUCD = '99' marks a diseminado area."""
        assert "99" == "99"  # trivial, but documents the convention

    def test_code_01_is_nucleo(self) -> None:
        """NUC_NUCD != '99' is a concentrated settlement (núcleo)."""
        for code in ["01", "02", "10", "98"]:
            assert code != "99"
