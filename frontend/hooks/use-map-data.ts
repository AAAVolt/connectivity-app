"use client";

import { apiFetch } from "@/lib/api";
import { mapKeys, STALE_TIMES } from "@/lib/query-keys";

/**
 * Query option factories for map data.
 *
 * These are not React hooks — they return query option objects
 * to be used with queryClient.ensureQueryData() or queryClient.prefetchQuery()
 * inside imperative map initialization code.
 */

export function boundaryQueryOptions(type: string) {
  return {
    queryKey: mapKeys.boundaries(type),
    queryFn: () => apiFetch<GeoJSON.FeatureCollection>(`/boundaries/${type}/geojson`),
    staleTime: STALE_TIMES.STATIC,
  };
}

export function destTypesQueryOptions() {
  return {
    queryKey: mapKeys.destTypes(),
    queryFn: () => apiFetch<Array<{ code: string; label: string }>>("/destinations/types"),
    staleTime: STALE_TIMES.STATIC,
  };
}

export function destinationsQueryOptions() {
  return {
    queryKey: mapKeys.destinations(),
    queryFn: () => apiFetch<GeoJSON.FeatureCollection>("/destinations/geojson"),
    staleTime: STALE_TIMES.STATIC,
  };
}

export function transitRoutesQueryOptions() {
  return {
    queryKey: mapKeys.transitRoutes(),
    queryFn: () => apiFetch<GeoJSON.FeatureCollection>("/transit/routes"),
    staleTime: STALE_TIMES.STATIC,
  };
}

export function transitStopsQueryOptions() {
  return {
    queryKey: mapKeys.transitStops(),
    queryFn: () => apiFetch<GeoJSON.FeatureCollection>("/transit/stops"),
    staleTime: STALE_TIMES.STATIC,
  };
}

export function nucleosQueryOptions() {
  return {
    queryKey: mapKeys.nucleos(),
    queryFn: () => apiFetch<GeoJSON.FeatureCollection>("/boundaries/nucleos/geojson"),
    staleTime: STALE_TIMES.STATIC,
  };
}

export function departureTimesQueryOptions() {
  return {
    queryKey: mapKeys.departureTimes(),
    queryFn: () => apiFetch<string[]>("/cells/departure-times"),
    staleTime: STALE_TIMES.STATIC,
  };
}

export function cellsQueryOptions(params: {
  mode?: string;
  purpose?: string;
  metric?: string;
  resolution?: number;
  departureTime?: string;
}) {
  const qs = new URLSearchParams();
  if (params.mode) qs.set("mode", params.mode);
  if (params.purpose) qs.set("purpose", params.purpose);
  if (params.metric === "travel_time") qs.set("metric", "travel_time");
  if (params.departureTime) qs.set("departure_time", params.departureTime);
  if (params.resolution && params.resolution !== 100) {
    qs.set("resolution", String(params.resolution));
  }
  const qsStr = qs.toString();
  return {
    queryKey: mapKeys.cells({
      mode: params.mode,
      purpose: params.purpose,
      metric: params.metric,
      resolution: String(params.resolution ?? 250),
      departureTime: params.departureTime,
    }),
    queryFn: () =>
      apiFetch<GeoJSON.FeatureCollection>(`/cells/geojson${qsStr ? `?${qsStr}` : ""}`),
    staleTime: STALE_TIMES.COMPUTED,
  };
}

export function frequencyQueryOptions(timeWindow: string, minDph = 0) {
  return {
    queryKey: mapKeys.frequency(timeWindow),
    queryFn: () =>
      apiFetch<GeoJSON.FeatureCollection>(
        `/sociodemographic/frequency/geojson?time_window=${timeWindow}&min_dph=${minDph}`,
      ),
    staleTime: STALE_TIMES.SESSION,
  };
}

export function socialMunisQueryOptions(departureTime?: string) {
  const qs = departureTime ? `?departure_time=${departureTime}` : "";
  return {
    queryKey: mapKeys.socialMunis(departureTime),
    queryFn: () =>
      apiFetch<GeoJSON.FeatureCollection>(`/sociodemographic/municipalities/geojson${qs}`),
    staleTime: STALE_TIMES.COMPUTED,
  };
}

export function socioProfilesQueryOptions() {
  return {
    queryKey: ["context", "profiles", "default"] as const,
    queryFn: () => apiFetch<Array<Record<string, unknown>>>("/sociodemographic/profiles"),
    staleTime: STALE_TIMES.COMPUTED,
  };
}
