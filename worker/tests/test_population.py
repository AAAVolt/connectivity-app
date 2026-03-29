"""Tests for population disaggregation (pure logic)."""

import pytest
from shapely.geometry import Polygon, box

from worker.pipeline.population import areal_weight_pure


class TestArealWeight:
    """Unit tests for the areal_weight_pure function."""

    def test_uniform_coverage_equal_allocation(self) -> None:
        """A source covering 4 equal cells allocates 25% to each."""
        source = box(0, 0, 200, 200)
        cells = [
            (1, box(0, 0, 100, 100)),
            (2, box(100, 0, 200, 100)),
            (3, box(0, 100, 100, 200)),
            (4, box(100, 100, 200, 200)),
        ]

        result = areal_weight_pure([(source, 1000.0)], cells)

        assert len(result) == 4
        for cell_id in [1, 2, 3, 4]:
            assert result[cell_id] == pytest.approx(250.0, rel=1e-6)

    def test_total_population_preserved(self) -> None:
        """Total allocated population equals total source population."""
        source1 = box(0, 0, 150, 150)
        source2 = box(120, 120, 300, 300)

        cells = [
            (1, box(0, 0, 100, 100)),
            (2, box(100, 0, 200, 100)),
            (3, box(0, 100, 100, 200)),
            (4, box(100, 100, 200, 200)),
            (5, box(200, 100, 300, 200)),
            (6, box(100, 200, 200, 300)),
            (7, box(200, 200, 300, 300)),
        ]

        total_source = 500.0 + 800.0
        result = areal_weight_pure(
            [(source1, 500.0), (source2, 800.0)],
            cells,
        )

        total_allocated = sum(result.values())
        assert total_allocated == pytest.approx(total_source, rel=1e-6)

    def test_partial_overlap_proportional(self) -> None:
        """Partial overlap allocates population proportionally by area."""
        source = box(0, 0, 100, 100)  # 100x100
        cell = box(50, 0, 150, 100)  # overlaps 50x100 = 50% of source

        result = areal_weight_pure([(source, 400.0)], [(1, cell)])

        assert result[1] == pytest.approx(200.0, rel=1e-6)

    def test_no_overlap_zero_population(self) -> None:
        """Cells outside all sources get zero population."""
        source = box(0, 0, 100, 100)
        cell = box(200, 200, 300, 300)

        result = areal_weight_pure([(source, 1000.0)], [(1, cell)])

        assert result[1] == pytest.approx(0.0)

    def test_multiple_sources_overlap_accumulates(self) -> None:
        """A cell overlapping multiple sources accumulates from both."""
        source1 = box(0, 0, 100, 100)  # 100x100, 500 pop
        source2 = box(50, 50, 150, 150)  # 100x100, 800 pop

        cell = box(0, 0, 100, 100)

        result = areal_weight_pure(
            [(source1, 500.0), (source2, 800.0)],
            [(1, cell)],
        )

        # From source1: 100% overlap → 500
        # From source2: (50*50)/(100*100) = 25% → 200
        assert result[1] == pytest.approx(700.0, rel=1e-6)

    def test_empty_sources_all_zero(self) -> None:
        """No sources means all cells get zero."""
        cell = box(0, 0, 100, 100)
        result = areal_weight_pure([], [(1, cell)])
        assert result[1] == pytest.approx(0.0)

    def test_zero_area_source_skipped(self) -> None:
        """A degenerate (zero-area) source is skipped safely."""
        source = Polygon()  # empty polygon, area = 0
        cell = box(0, 0, 100, 100)

        result = areal_weight_pure([(source, 1000.0)], [(1, cell)])

        assert result[1] == pytest.approx(0.0)

    def test_single_cell_full_coverage(self) -> None:
        """A cell fully inside a source gets its proportional share."""
        source = box(0, 0, 300, 300)  # 300x300 = 90000 area
        cell = box(100, 100, 200, 200)  # 100x100 = 10000 area

        result = areal_weight_pure([(source, 9000.0)], [(1, cell)])

        # Cell covers 10000/90000 = 1/9 of source
        expected = 9000.0 * (10000.0 / 90000.0)
        assert result[1] == pytest.approx(expected, rel=1e-6)
