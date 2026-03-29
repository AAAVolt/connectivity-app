"""Integration-style tests for the scoring pipeline (pure logic, no DB)."""

import pytest

from worker.scoring.diminishing import concave_transform
from worker.scoring.impedance import exponential_impedance


class TestScoringInvariants:
    """Verify key scoring invariants using pure functions."""

    ALPHA = 0.05
    BETA = 0.7

    def _cell_score(self, travel_times: list[float], weight: float = 1.0) -> float:
        """Compute score for a single cell given travel times to destinations."""
        raw = sum(weight * exponential_impedance(t, self.ALPHA) for t in travel_times)
        return concave_transform(raw, self.BETA)

    def test_closer_destinations_higher_score(self) -> None:
        """A cell with a closer destination scores higher."""
        score_close = self._cell_score([5.0])
        score_far = self._cell_score([30.0])
        assert score_close > score_far

    def test_more_destinations_higher_score(self) -> None:
        """More reachable destinations → higher score."""
        score_1 = self._cell_score([10.0])
        score_2 = self._cell_score([10.0, 20.0])
        score_3 = self._cell_score([10.0, 20.0, 30.0])
        assert score_3 > score_2 > score_1

    def test_diminishing_marginal_impact(self) -> None:
        """Each additional destination adds less to the score."""
        score_0 = 0.0
        score_1 = self._cell_score([10.0])
        score_2 = self._cell_score([10.0, 10.0])
        score_3 = self._cell_score([10.0, 10.0, 10.0])

        gain_1 = score_1 - score_0
        gain_2 = score_2 - score_1
        gain_3 = score_3 - score_2

        assert gain_2 < gain_1
        assert gain_3 < gain_2

    def test_weight_scales_contribution(self) -> None:
        """Higher destination weight → higher score."""
        score_low = self._cell_score([10.0], weight=1.0)
        score_high = self._cell_score([10.0], weight=5.0)
        assert score_high > score_low

    def test_unreachable_destination_zero_contribution(self) -> None:
        """A destination at exactly 60 min contributes very little."""
        impedance_at_60 = exponential_impedance(60.0, self.ALPHA)
        assert impedance_at_60 < 0.06  # exp(-3) ≈ 0.05

    def test_normalization_invariant(self) -> None:
        """Min-max normalization maps to [0, 100]."""
        scores = [self._cell_score([t]) for t in [5, 10, 20, 30, 45, 60]]

        mn, mx = min(scores), max(scores)
        normalized = [(s - mn) / (mx - mn) * 100 for s in scores]

        assert normalized[0] == pytest.approx(100.0)  # closest = best
        assert normalized[-1] == pytest.approx(0.0)  # farthest = worst
        assert all(0 <= n <= 100 for n in normalized)
