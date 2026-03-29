"""Impedance functions for accessibility scoring."""

import math


def exponential_impedance(travel_time: float, alpha: float) -> float:
    """Compute exponential impedance: exp(-alpha * t).

    Returns a value in (0, 1] where:
      - t = 0  → 1.0  (zero travel time = full accessibility)
      - t → ∞  → 0.0  (infinite travel time = no accessibility)

    Args:
        travel_time: Travel time in minutes (>= 0).
        alpha: Decay rate (> 0). Higher = faster decay.

    Raises:
        ValueError: If travel_time < 0 or alpha <= 0.
    """
    if travel_time < 0:
        raise ValueError(f"travel_time must be >= 0, got {travel_time}")
    if alpha <= 0:
        raise ValueError(f"alpha must be > 0, got {alpha}")
    return math.exp(-alpha * travel_time)
