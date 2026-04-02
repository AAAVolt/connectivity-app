"""Tests for population disaggregation (pure logic)."""

import pytest
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from worker.pipeline.population import areal_weight_pure, dasymetric_weight_pure


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


# ---------------------------------------------------------------------------
# Dasymetric masking tests
# ---------------------------------------------------------------------------

class TestDasymetricWeight:
    """Unit tests for dasymetric_weight_pure (núcleo-masked disaggregation)."""

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

    def test_mask_covers_source_same_as_areal(self) -> None:
        """When mask fully covers the source, result equals plain areal."""
        source = box(0, 0, 200, 200)
        mask = box(0, 0, 300, 300)  # bigger than source
        cells = self._make_grid(0, 0, 2, 2)

        dasy = dasymetric_weight_pure([(source, 1000.0)], cells, mask)
        areal = areal_weight_pure([(source, 1000.0)], cells)

        for cid in [1, 2, 3, 4]:
            assert dasy[cid] == pytest.approx(areal[cid], rel=1e-6)

    def test_cells_outside_mask_get_zero(self) -> None:
        """Cells in diseminado (outside mask) receive zero population."""
        source = box(0, 0, 200, 200)
        # Mask covers only the left half of the source
        mask = box(0, 0, 100, 200)
        cells = self._make_grid(0, 0, 2, 2)
        # _make_grid is column-major: ix=0 → cells 1,2; ix=1 → cells 3,4

        result = dasymetric_weight_pure([(source, 1000.0)], cells, mask)

        # Cells 1 and 2 (x=0..100) are inside mask
        assert result[1] > 0
        assert result[2] > 0
        # Cells 3 and 4 (x=100..200) are outside mask → zero
        assert result[3] == pytest.approx(0.0)
        assert result[4] == pytest.approx(0.0)

    def test_population_concentrates_in_masked_area(self) -> None:
        """All source population is redistributed into the masked area."""
        source = box(0, 0, 200, 200)
        mask = box(0, 0, 100, 200)  # left half
        cells = self._make_grid(0, 0, 2, 2)
        pop = 1000.0

        result = dasymetric_weight_pure([(source, pop)], cells, mask)

        # Source fully contains mask, so all pop goes to masked cells
        total = sum(result.values())
        assert total == pytest.approx(pop, rel=1e-6)

    def test_no_double_counting_overlapping_nucleos(self) -> None:
        """Overlapping núcleos merged via union don't cause double counting."""
        source = box(0, 0, 200, 200)
        # Two overlapping núcleos — union them (as the SQL does)
        nucleo1 = box(0, 0, 150, 200)
        nucleo2 = box(50, 0, 200, 200)
        mask = unary_union([nucleo1, nucleo2])  # covers 0..200

        cells = self._make_grid(0, 0, 2, 2)
        pop = 1000.0

        result = dasymetric_weight_pure([(source, pop)], cells, mask)

        total = sum(result.values())
        assert total == pytest.approx(pop, rel=1e-6)
        # Each cell should get 25% (mask covers entire source)
        for cid in [1, 2, 3, 4]:
            assert result[cid] == pytest.approx(250.0, rel=1e-6)

    def test_no_double_counting_cell_in_multiple_source_mask_overlaps(self) -> None:
        """A cell overlapping two sources gets correct sum, not double."""
        # Two adjacent, non-overlapping sources
        source1 = box(0, 0, 100, 200)    # pop 600
        source2 = box(100, 0, 200, 200)  # pop 400
        # Mask covers a strip in the middle (overlaps both sources)
        mask = box(50, 0, 150, 200)

        cells = self._make_grid(0, 0, 2, 2)
        pop1, pop2 = 600.0, 400.0

        result = dasymetric_weight_pure(
            [(source1, pop1), (source2, pop2)], cells, mask
        )

        total = sum(result.values())
        # Total = pop1 + pop2 = 1000 (both sources fully contain their mask part)
        assert total == pytest.approx(1000.0, rel=1e-6)

    def test_partial_mask_loses_diseminado_population(self) -> None:
        """Population in diseminado (outside mask) is intentionally lost."""
        source = box(0, 0, 200, 200)
        # Mask covers only a quarter of the source
        mask = box(0, 0, 100, 100)
        cells = self._make_grid(0, 0, 2, 2)
        pop = 400.0

        result = dasymetric_weight_pure([(source, pop)], cells, mask)

        # Only cell 1 intersects the mask
        assert result[1] == pytest.approx(pop, rel=1e-6)
        assert result[2] == pytest.approx(0.0)
        assert result[3] == pytest.approx(0.0)
        assert result[4] == pytest.approx(0.0)
        # Total allocated = source pop (mask is fully inside source)
        assert sum(result.values()) == pytest.approx(pop, rel=1e-6)

    def test_mask_partially_outside_source_still_conserves(self) -> None:
        """When mask extends beyond source, only source ∩ mask area matters."""
        source = box(0, 0, 100, 100)
        # Mask extends beyond source on right side
        mask = box(50, 0, 200, 100)
        cell = box(50, 0, 100, 100)  # inside both source and mask
        pop = 500.0

        result = dasymetric_weight_pure([(source, pop)], [(1, cell)], mask)

        # masked_src = source ∩ mask = box(50,0,100,100), area = 50*100 = 5000
        # cell ∩ masked_src = box(50,0,100,100), area = 5000
        # proportion = 5000/5000 = 1.0 → cell gets full pop
        assert result[1] == pytest.approx(pop, rel=1e-6)

    def test_empty_mask_all_zero(self) -> None:
        """An empty mask means no cells get population."""
        source = box(0, 0, 200, 200)
        mask = Polygon()  # empty
        cells = self._make_grid(0, 0, 2, 2)

        result = dasymetric_weight_pure([(source, 1000.0)], cells, mask)

        for cid in result:
            assert result[cid] == pytest.approx(0.0)

    def test_mask_disjoint_from_source_all_zero(self) -> None:
        """When mask doesn't intersect source, no population allocated."""
        source = box(0, 0, 100, 100)
        mask = box(500, 500, 600, 600)  # far away
        cell = box(0, 0, 100, 100)

        result = dasymetric_weight_pure([(source, 1000.0)], [(1, cell)], mask)
        assert result[1] == pytest.approx(0.0)

    def test_multiple_nucleos_non_overlapping(self) -> None:
        """Two separate núcleos concentrate population into two clusters."""
        source = box(0, 0, 400, 100)  # long strip, 4 cells
        nucleo_left = box(0, 0, 100, 100)
        nucleo_right = box(300, 0, 400, 100)
        mask = unary_union([nucleo_left, nucleo_right])

        cells = [
            (1, box(0, 0, 100, 100)),
            (2, box(100, 0, 200, 100)),
            (3, box(200, 0, 300, 100)),
            (4, box(300, 0, 400, 100)),
        ]
        pop = 2000.0

        result = dasymetric_weight_pure([(source, pop)], cells, mask)

        # Only cells 1 and 4 overlap the mask
        assert result[1] == pytest.approx(1000.0, rel=1e-6)
        assert result[2] == pytest.approx(0.0)
        assert result[3] == pytest.approx(0.0)
        assert result[4] == pytest.approx(1000.0, rel=1e-6)
        assert sum(result.values()) == pytest.approx(pop, rel=1e-6)

    def test_conservation_multiple_sources_and_nucleos(self) -> None:
        """Complex scenario: 2 sources, 2 núcleos, 6 cells — no double count."""
        source1 = box(0, 0, 200, 100)    # 200×100, pop 1000
        source2 = box(200, 0, 400, 100)  # 200×100, pop 500
        nucleo1 = box(50, 0, 150, 100)   # overlaps source1
        nucleo2 = box(250, 0, 350, 100)  # overlaps source2
        mask = unary_union([nucleo1, nucleo2])

        cells = [
            (i + 1, box(i * 100, 0, (i + 1) * 100, 100))
            for i in range(4)
        ]
        result = dasymetric_weight_pure(
            [(source1, 1000.0), (source2, 500.0)], cells, mask
        )

        # Source1 masked area = box(50,0,150,100) = 100×100 = 10000
        # Source2 masked area = box(250,0,350,100) = 100×100 = 10000
        # Total allocated should be 1000 + 500 = 1500
        total = sum(result.values())
        assert total == pytest.approx(1500.0, rel=1e-6)

        # Cell 1 (0..100): overlaps masked_src1 by box(50,0,100,100)=50×100
        # → 1000 * 5000/10000 = 500
        assert result[1] == pytest.approx(500.0, rel=1e-6)
        # Cell 2 (100..200): overlaps masked_src1 by box(100,0,150,100)=50×100
        # → 1000 * 5000/10000 = 500
        assert result[2] == pytest.approx(500.0, rel=1e-6)
        # Cell 3 (200..300): overlaps masked_src2 by box(250,0,300,100)=50×100
        # → 500 * 5000/10000 = 250
        assert result[3] == pytest.approx(250.0, rel=1e-6)
        # Cell 4 (300..400): overlaps masked_src2 by box(300,0,350,100)=50×100
        # → 500 * 5000/10000 = 250
        assert result[4] == pytest.approx(250.0, rel=1e-6)
