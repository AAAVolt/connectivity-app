"""Scoring configuration loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


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

    return ScoringConfig(
        purpose_map=raw["purpose_map"],
        impedance=raw["impedance"],
        beta=raw["diminishing"]["beta"],
        max_travel_time=raw["max_travel_time"],
        combined_weights=raw["combined_weights"],
    )
