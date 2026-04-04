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

// ── Sociodemographic API types ──

export interface MunicipalityDemographics {
  muni_code: string;
  name: string;
  year: number;
  pop_total: number;
  pop_0_17: number;
  pop_18_25: number;
  pop_26_64: number;
  pop_65_plus: number;
  pct_0_17: number;
  pct_18_25: number;
  pct_65_plus: number;
}

export interface MunicipalityIncome {
  muni_code: string;
  name: string;
  year: number;
  renta_personal_media: number | null;
  renta_disponible_media: number | null;
  renta_index: number | null;
}

export interface MunicipalityCarOwnership {
  muni_code: string;
  name: string;
  year: number;
  vehicles_per_inhab: number;
}

export interface MunicipalitySocioProfile {
  muni_code: string;
  name: string;
  pop_total: number | null;
  pop_0_17: number | null;
  pop_18_25: number | null;
  pop_65_plus: number | null;
  pct_0_17: number | null;
  pct_18_25: number | null;
  pct_65_plus: number | null;
  renta_personal_media: number | null;
  renta_disponible_media: number | null;
  renta_index: number | null;
  vehicles_per_inhab: number | null;
  weighted_avg_score: number | null;
  population: number | null;
}

export interface FrequencyGeoJSON {
  type: string;
  features: Array<{
    type: string;
    geometry: { type: string; coordinates: [number, number] };
    properties: {
      operator: string;
      stop_id: string;
      stop_name: string | null;
      departures: number;
      departures_per_hour: number;
    };
  }>;
}

// ── Sociodemographic API functions ──

export function getDemographics(
  year = 2025,
): Promise<MunicipalityDemographics[]> {
  return apiFetch<MunicipalityDemographics[]>(
    `/sociodemographic/demographics?year=${year}`,
  );
}

export function getIncome(year?: number): Promise<MunicipalityIncome[]> {
  const qs = year ? `?year=${year}` : "";
  return apiFetch<MunicipalityIncome[]>(`/sociodemographic/income${qs}`);
}

export function getCarOwnership(
  year?: number,
): Promise<MunicipalityCarOwnership[]> {
  const qs = year ? `?year=${year}` : "";
  return apiFetch<MunicipalityCarOwnership[]>(
    `/sociodemographic/car-ownership${qs}`,
  );
}

export function getSocioProfiles(): Promise<MunicipalitySocioProfile[]> {
  return apiFetch<MunicipalitySocioProfile[]>(`/sociodemographic/profiles`);
}

export function getFrequencyGeoJSON(
  timeWindow = "07:00-09:00",
  minDph = 0,
): Promise<FrequencyGeoJSON> {
  return apiFetch<FrequencyGeoJSON>(
    `/sociodemographic/frequency/geojson?time_window=${timeWindow}&min_dph=${minDph}`,
  );
}
