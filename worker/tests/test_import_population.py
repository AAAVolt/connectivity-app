"""Tests for census section population import and disaggregation totals."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from shapely.geometry import MultiPolygon, Polygon, box

from worker.pipeline.import_population import (
    _ensure_multi,
    parse_population_csv,
)
from worker.pipeline.population import areal_weight_pure


# ---------------------------------------------------------------------------
# CSV parser tests
# ---------------------------------------------------------------------------

class TestParsePopulationCSV:
    """Tests for parse_population_csv."""

    def _write_csv(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "pop.csv"
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    def test_basic_parsing(self, tmp_path: Path) -> None:
        """Parses well-formed CSV and builds correct join keys."""
        csv = self._write_csv(tmp_path, """\
            header1
            header2
            header3
            header4
            header5
            "kod.";"Udalerria";"Barr.";"Sezk."
            001;"Abadiño";01;000;7.800;rest
            ;;;001;1.544;rest
            ;;;002;1.238;rest
            002;"Abanto";01;000;4.972;rest
            ;;;001;1.791;rest
        """)
        result = parse_population_csv(csv)
        assert result == {
            "4800101001": 1544,
            "4800101002": 1238,
            "4800201001": 1791,
        }

    def test_totals_skipped(self, tmp_path: Path) -> None:
        """Section '000' (district totals) are excluded."""
        csv = self._write_csv(tmp_path, """\
            h1
            h2
            h3
            h4
            h5
            header
            001;"Muni";01;000;5.000;rest
            ;;;001;3.000;rest
            ;;;002;2.000;rest
        """)
        result = parse_population_csv(csv)
        assert len(result) == 2
        assert sum(result.values()) == 5000

    def test_population_total_matches_sum(self, tmp_path: Path) -> None:
        """Sum of parsed sections equals the known total."""
        csv = self._write_csv(tmp_path, """\
            h1
            h2
            h3
            h4
            h5
            header
            001;"A";01;000;100;x
            ;;;001;40;x
            ;;;002;60;x
            002;"B";01;000;200;x
            ;;;001;200;x
        """)
        result = parse_population_csv(csv)
        assert sum(result.values()) == 300

    def test_empty_csv(self, tmp_path: Path) -> None:
        """Empty CSV returns empty dict."""
        csv = self._write_csv(tmp_path, """\
            h1
            h2
            h3
            h4
            h5
            header
        """)
        result = parse_population_csv(csv)
        assert result == {}

    def test_district_carry_forward(self, tmp_path: Path) -> None:
        """District code carries forward across rows within a municipality."""
        csv = self._write_csv(tmp_path, """\
            h1
            h2
            h3
            h4
            h5
            header
            020;"Bilbao";01;000;10.000;x
            ;;;001;5.000;x
            ;;02;000;8.000;x
            ;;;001;4.000;x
            ;;;002;4.000;x
        """)
        result = parse_population_csv(csv)
        assert "4802001001" in result
        assert "4802002001" in result
        assert "4802002002" in result
        assert result["4802001001"] == 5000
        assert result["4802002001"] == 4000


# ---------------------------------------------------------------------------
# Geometry helper tests
# ---------------------------------------------------------------------------

class TestEnsureMulti:
    """Tests for _ensure_multi geometry promotion."""

    def test_polygon_promoted(self) -> None:
        p = box(0, 0, 1, 1)
        result = _ensure_multi(p)
        assert isinstance(result, MultiPolygon)
        assert len(result.geoms) == 1

    def test_multipolygon_passthrough(self) -> None:
        mp = MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])
        result = _ensure_multi(mp)
        assert result is mp

    def test_none_returns_empty(self) -> None:
        result = _ensure_multi(None)
        assert isinstance(result, MultiPolygon)
        assert result.is_empty

    def test_geometry_collection_extracts_polygons(self) -> None:
        """GeometryCollection (from make_valid) extracts polygon parts."""
        from shapely.geometry import GeometryCollection, LineString

        gc = GeometryCollection([
            MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)]),
            LineString([(0, 0), (1, 1)]),  # non-polygon part, discarded
        ])
        result = _ensure_multi(gc)
        assert isinstance(result, MultiPolygon)
        assert len(result.geoms) == 2
        assert result.area > 0


# ---------------------------------------------------------------------------
# Disaggregation: total preservation tests
# ---------------------------------------------------------------------------

class TestDisaggregationTotals:
    """Verify population totals are preserved in various scenarios."""

    def _make_grid(
        self, x0: float, y0: float, nx: int, ny: int, size: float = 100
    ) -> list[tuple[int, Polygon]]:
        """Generate a regular grid of cells."""
        cells = []
        cid = 1
        for ix in range(nx):
            for iy in range(ny):
                cells.append((
                    cid,
                    box(x0 + ix * size, y0 + iy * size,
                        x0 + (ix + 1) * size, y0 + (iy + 1) * size),
                ))
                cid += 1
        return cells

    def test_source_smaller_than_cell(self) -> None:
        """A source polygon smaller than one cell preserves total."""
        source = box(30, 30, 70, 70)  # 40x40 = 1600 m²
        cell = box(0, 0, 100, 100)  # 100x100 = 10000 m²
        pop = 500.0

        result = areal_weight_pure([(source, pop)], [(1, cell)])
        # Source is fully inside cell → cell gets 100% of source pop
        assert result[1] == pytest.approx(pop, rel=1e-6)

    def test_tiny_source_straddling_four_cells(self) -> None:
        """A tiny source centered on the junction of 4 cells."""
        source = box(90, 90, 110, 110)  # 20x20 = 400 m²
        cells = self._make_grid(0, 0, 2, 2)
        pop = 47.0

        result = areal_weight_pure([(source, pop)], cells)
        total = sum(result.values())
        assert total == pytest.approx(pop, rel=1e-6)

    def test_many_small_sources_on_large_grid(self) -> None:
        """Multiple small sources scattered across a large grid."""
        cells = self._make_grid(0, 0, 10, 10)  # 100 cells

        sources = [
            (box(50, 50, 80, 80), 100.0),     # inside cell (0,0)
            (box(150, 250, 180, 280), 200.0),  # inside cell (1,2)
            (box(490, 490, 510, 510), 300.0),  # straddles 4 cells
            (box(0, 0, 1000, 1000), 1000.0),   # covers all cells
        ]
        total_source = sum(p for _, p in sources)

        result = areal_weight_pure(sources, cells)
        total_alloc = sum(result.values())
        assert total_alloc == pytest.approx(total_source, rel=1e-6)

    def test_irregular_triangle_source(self) -> None:
        """An irregular (non-rectangular) source still preserves totals."""
        triangle = Polygon([(0, 0), (200, 0), (100, 200)])
        cells = self._make_grid(0, 0, 2, 2)
        pop = 750.0

        result = areal_weight_pure([(triangle, pop)], cells)
        total = sum(result.values())
        assert total == pytest.approx(pop, rel=1e-4)

    def test_concave_source(self) -> None:
        """A concave (L-shaped) source preserves totals."""
        l_shape = Polygon([
            (0, 0), (200, 0), (200, 100),
            (100, 100), (100, 200), (0, 200),
        ])
        cells = self._make_grid(0, 0, 2, 2)
        pop = 600.0

        result = areal_weight_pure([(l_shape, pop)], cells)
        total = sum(result.values())
        assert total == pytest.approx(pop, rel=1e-4)

    def test_source_at_grid_edge_partial_coverage(self) -> None:
        """Source extending beyond grid loses population proportionally."""
        # Grid covers (0,0)-(100,100) but source extends to (150,150)
        source = box(0, 0, 150, 150)
        cells = [(1, box(0, 0, 100, 100))]
        pop = 900.0

        result = areal_weight_pure([(source, pop)], cells)
        # Cell covers (100*100)/(150*150) = 44.4% of source
        expected = pop * (100 * 100) / (150 * 150)
        assert result[1] == pytest.approx(expected, rel=1e-6)

        # Total allocated is LESS than source — expected loss
        assert sum(result.values()) < pop

    def test_adjacent_sources_no_double_counting(self) -> None:
        """Adjacent (non-overlapping) sources don't double-count."""
        source1 = box(0, 0, 100, 100)
        source2 = box(100, 0, 200, 100)
        cells = self._make_grid(0, 0, 2, 1)

        result = areal_weight_pure(
            [(source1, 500.0), (source2, 300.0)],
            cells,
        )
        total = sum(result.values())
        assert total == pytest.approx(800.0, rel=1e-6)

    def test_multipolygon_source_preserves_total(self) -> None:
        """A MultiPolygon source (treated as single Shapely geom) preserves totals."""
        mp = MultiPolygon([box(0, 0, 50, 100), box(50, 0, 100, 100)])
        cells = [(1, box(0, 0, 100, 100))]
        pop = 1000.0

        result = areal_weight_pure([(mp, pop)], cells)
        assert result[1] == pytest.approx(pop, rel=1e-6)


# ---------------------------------------------------------------------------
# Density reasonableness checks
# ---------------------------------------------------------------------------

class TestDensityReasonableness:
    """Sanity checks on population density after disaggregation."""

    def test_density_proportional_to_coverage(self) -> None:
        """Cells partially covered by a source get proportionally less pop."""
        source = box(0, 0, 150, 100)  # covers 1.5 cells wide
        cells = [
            (1, box(0, 0, 100, 100)),    # fully covered
            (2, box(100, 0, 200, 100)),   # 50% covered
        ]
        pop = 3000.0

        result = areal_weight_pure([(source, pop)], cells)

        # Cell 1 gets 2/3 of pop (100/150), cell 2 gets 1/3 (50/150)
        assert result[1] == pytest.approx(2000.0, rel=1e-6)
        assert result[2] == pytest.approx(1000.0, rel=1e-6)

    def test_no_cell_exceeds_source_population(self) -> None:
        """No single cell can receive more than its source's total population."""
        source = box(10, 10, 90, 90)  # well inside one cell
        cells = self._make_grid(0, 0, 3, 3)
        pop = 500.0

        result = areal_weight_pure([(source, pop)], cells)

        for cell_pop in result.values():
            assert cell_pop <= pop + 0.01  # allow FP tolerance

    def test_bizkaia_scale_density_check(self) -> None:
        """Simulate Bizkaia-scale: 1.15M people across ~22,000 cells ≈ 52 avg."""
        # Not a real spatial test, just a sanity check on the math
        total_pop = 1_155_733
        total_cells = 22_100  # approx 100m cells covering Bizkaia

        avg_density = total_pop / total_cells
        assert 40 < avg_density < 70  # reasonable range

    def _make_grid(
        self, x0: float, y0: float, nx: int, ny: int, size: float = 100
    ) -> list[tuple[int, Polygon]]:
        cells = []
        cid = 1
        for ix in range(nx):
            for iy in range(ny):
                cells.append((
                    cid,
                    box(x0 + ix * size, y0 + iy * size,
                        x0 + (ix + 1) * size, y0 + (iy + 1) * size),
                ))
                cid += 1
        return cells
