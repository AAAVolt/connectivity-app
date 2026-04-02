const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";

interface RequestOptions {
  tenantId?: string;
  token?: string;
  method?: string;
  body?: unknown;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  headers["X-Tenant-ID"] = options.tenantId ?? DEMO_TENANT;

  if (options.token) {
    headers["Authorization"] = `Bearer ${options.token}`;
  }

  const init: RequestInit = { headers };
  if (options.method) init.method = options.method;
  if (options.body) init.body = JSON.stringify(options.body);

  const response = await fetch(`${API_BASE}${path}`, init);

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

// ── Typed API functions ──

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

export function getCell(cellId: number | string): Promise<CellResponse> {
  return apiFetch<CellResponse>(`/cells/${cellId}`);
}

export function postStatsArea(
  geometry: GeoJSON.Geometry,
): Promise<AreaStatsResponse> {
  return apiFetch<AreaStatsResponse>("/stats/area", {
    method: "POST",
    body: { geometry },
  });
}

// ── Dashboard API types ──

export interface DashboardSummary {
  total_cells: number;
  populated_cells: number;
  total_population: number;
  cells_with_scores: number;
  avg_score: number | null;
  weighted_avg_score: number | null;
  median_score: number | null;
  destination_count: number;
  transit_stop_count: number;
  transit_route_count: number;
  municipality_count: number;
  comarca_count: number;
}

export interface ScoreDistributionBucket {
  range_label: string;
  range_min: number;
  range_max: number;
  cell_count: number;
  population: number;
}

export interface PurposeBreakdown {
  mode: string;
  purpose: string;
  purpose_label: string;
  avg_score: number | null;
  weighted_avg_score: number | null;
  avg_travel_time: number | null;
  cell_count: number;
}

export interface ServiceCoverage {
  purpose: string;
  purpose_label: string;
  mode: string;
  total_cells: number;
  total_population: number;
  pop_15min: number;
  pop_30min: number;
  pop_45min: number;
  pop_60min: number;
  pct_pop_15min: number;
  pct_pop_30min: number;
  pct_pop_45min: number;
  pct_pop_60min: number;
  avg_travel_time: number | null;
  median_travel_time: number | null;
}

// ── Dashboard API functions ──

export function getDashboardSummary(
  departureTime = "08:00",
): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>(
    `/dashboard/summary?departure_time=${departureTime}`,
  );
}

export function getScoreDistribution(
  departureTime = "08:00",
): Promise<ScoreDistributionBucket[]> {
  return apiFetch<ScoreDistributionBucket[]>(
    `/dashboard/score-distribution?departure_time=${departureTime}`,
  );
}

export function getPurposeBreakdown(
  departureTime = "08:00",
): Promise<PurposeBreakdown[]> {
  return apiFetch<PurposeBreakdown[]>(
    `/dashboard/purpose-breakdown?departure_time=${departureTime}`,
  );
}

export function getServiceCoverage(
  departureTime = "08:00",
): Promise<ServiceCoverage[]> {
  return apiFetch<ServiceCoverage[]>(
    `/dashboard/service-coverage?departure_time=${departureTime}`,
  );
}
