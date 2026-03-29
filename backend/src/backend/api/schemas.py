"""Pydantic response and request schemas for API endpoints."""

from pydantic import BaseModel


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


class AreaStatsRequest(BaseModel):
    geometry: dict  # GeoJSON geometry object


class AreaStatsResponse(BaseModel):
    cell_count: int
    population: float
    avg_combined_score: float | None
    weighted_avg_combined_score: float | None
