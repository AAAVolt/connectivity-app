export interface GridCell {
  id: number;
  cellCode: string;
  population: number;
  geometry: GeoJSON.Polygon;
}

export interface CellScoreDetail {
  mode: string;
  purpose: string;
  score: number;
  score_normalized: number | null;
}

export interface CellResponse {
  id: number;
  cell_code: string;
  population: number;
  combined_score: number | null;
  combined_score_normalized: number | null;
  scores: CellScoreDetail[];
}

export interface AreaStatsResponse {
  cell_count: number;
  population: number;
  avg_combined_score: number | null;
  weighted_avg_combined_score: number | null;
}

export interface ConnectivityScore {
  cell_id: number;
  mode: "TRANSIT";
  purpose: string;
  score: number;
  score_normalized: number | null;
}

export interface CombinedScore {
  cell_id: number;
  combined_score: number;
  combined_score_normalized: number | null;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}
