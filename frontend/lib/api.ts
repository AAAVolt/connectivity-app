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
