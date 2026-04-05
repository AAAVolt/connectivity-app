"""Pydantic response and request schemas for API endpoints."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, field_validator

_logger = logging.getLogger(__name__)


def parse_geometry(raw: str | None) -> dict[str, Any] | None:
    """Safely parse a GeoJSON geometry string from the database.

    Returns None (instead of crashing) if the string is missing or malformed.
    """
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        _logger.warning("Malformed geometry JSON, skipping: %.80s", raw)
        return None


class CellScoreDetail(BaseModel):
    mode: str
    purpose: str
    score: float
    score_normalized: float | None


class CellResponse(BaseModel):
    id: int
    cell_code: str
    population: float
    combined_score: float | None
    combined_score_normalized: float | None
    scores: list[CellScoreDetail]


_GEOJSON_GEOMETRY_TYPES = frozenset({
    "Point", "MultiPoint", "LineString", "MultiLineString",
    "Polygon", "MultiPolygon", "GeometryCollection",
})


class AreaStatsRequest(BaseModel):
    geometry: dict  # GeoJSON geometry object

    @field_validator("geometry")
    @classmethod
    def _validate_geojson(cls, v: dict) -> dict:
        geo_type = v.get("type")
        if geo_type not in _GEOJSON_GEOMETRY_TYPES:
            raise ValueError(
                f"Invalid GeoJSON geometry type: {geo_type!r}. "
                f"Must be one of {sorted(_GEOJSON_GEOMETRY_TYPES)}"
            )
        if "coordinates" not in v and geo_type != "GeometryCollection":
            raise ValueError("GeoJSON geometry must include 'coordinates'")
        if geo_type == "GeometryCollection" and "geometries" not in v:
            raise ValueError("GeometryCollection must include 'geometries'")
        return v


class AreaStatsResponse(BaseModel):
    cell_count: int
    population: float
    avg_combined_score: float | None
    weighted_avg_combined_score: float | None
