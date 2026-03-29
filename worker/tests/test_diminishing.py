"""Tests for the concave (diminishing returns) transform."""

import pytest

from worker.scoring.diminishing import concave_transform


class TestConcaveTransform:

    def test_zero_input_zero_output(self) -> None:
        assert concave_transform(0, 0.7) == 0.0

    def test_positive_output_for_positive_input(self) -> None:
        assert concave_transform(10, 0.7) > 0

    def test_diminishing_marginal_gains(self) -> None:
        beta = 0.7
        v1 = concave_transform(10, beta)
        v2 = concave_transform(20, beta)
        gain_first = v1  # 0 → 10
        gain_second = v2 - v1  # 10 → 20
        assert gain_second < gain_first

    def test_beta_near_one_almost_linear(self) -> None:
        assert concave_transform(100, 0.99) == pytest.approx(
            100 ** 0.99, rel=1e-6
        )

    def test_concavity_holds_across_range(self) -> None:
        beta = 0.7
        prev_gain = float("inf")
        prev_val = 0.0
        for x in range(10, 110, 10):
            val = concave_transform(x, beta)
            gain = val - prev_val
            assert gain < prev_gain
            prev_gain = gain
            prev_val = val

    def test_negative_score_raises(self) -> None:
        with pytest.raises(ValueError, match="raw_score"):
            concave_transform(-1, 0.7)

    def test_beta_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="beta"):
            concave_transform(10, 0)

    def test_beta_one_raises(self) -> None:
        with pytest.raises(ValueError, match="beta"):
            concave_transform(10, 1.0)

    def test_beta_greater_than_one_raises(self) -> None:
        with pytest.raises(ValueError, match="beta"):
            concave_transform(10, 1.5)
