"""Tests for the exponential impedance function."""

import pytest

from worker.scoring.impedance import exponential_impedance


class TestExponentialImpedance:

    def test_zero_travel_time_returns_one(self) -> None:
        assert exponential_impedance(0, 0.05) == pytest.approx(1.0)

    def test_positive_time_less_than_one(self) -> None:
        val = exponential_impedance(10, 0.05)
        assert 0 < val < 1.0

    def test_higher_alpha_faster_decay(self) -> None:
        slow = exponential_impedance(10, 0.03)
        fast = exponential_impedance(10, 0.08)
        assert fast < slow

    def test_monotonically_decreasing(self) -> None:
        alpha = 0.05
        prev = 1.0
        for t in range(1, 61):
            val = exponential_impedance(t, alpha)
            assert val < prev
            prev = val

    def test_large_travel_time_approaches_zero(self) -> None:
        val = exponential_impedance(120, 0.05)
        assert val < 0.01

    def test_negative_travel_time_raises(self) -> None:
        with pytest.raises(ValueError, match="travel_time"):
            exponential_impedance(-1, 0.05)

    def test_zero_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            exponential_impedance(10, 0)

    def test_negative_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            exponential_impedance(10, -0.05)
