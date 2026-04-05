"""Scoring configuration loaded from YAML."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoringConfig:
    """Immutable scoring parameters."""

    purpose_map: dict[str, str]
    impedance: dict[str, dict[str, float]]
    beta: float
    max_travel_time: float
    combined_weights: dict[str, dict[str, float]]


def load_scoring_config(path: Path | None = None) -> ScoringConfig:
    """Load scoring config from a YAML file.

    Default path: worker/config/scoring.yaml (resolved relative to
    this file's package root, which works both locally and in Docker).
    """
    if path is None:
        path = Path(__file__).parents[3] / "config" / "scoring.yaml"

    with open(path) as f:
        raw = yaml.safe_load(f)

    combined_weights: dict[str, dict[str, float]] = raw["combined_weights"]

    # Warn if weights per mode don't sum to ~1.0 (will be normalised at
    # scoring time, but the config comment says "must sum to 1.0").
    for mode, purposes in combined_weights.items():
        total = sum(purposes.values())
        if abs(total - 1.0) > 0.01:
            _logger.warning(
                "combined_weights for mode %s sum to %.3f (expected ~1.0); "
                "the scoring engine will normalise dynamically based on "
                "which purpose types are present in the data.",
                mode,
                total,
            )

    return ScoringConfig(
        purpose_map=raw["purpose_map"],
        impedance=raw["impedance"],
        beta=raw["diminishing"]["beta"],
        max_travel_time=raw["max_travel_time"],
        combined_weights=combined_weights,
    )
