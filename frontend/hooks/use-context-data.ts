"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { MunicipalitySocioProfile } from "@/lib/api";

export const contextKeys = {
  all: ["context"] as const,
  profiles: () => [...contextKeys.all, "profiles"] as const,
  frequency: (window: string) =>
    [...contextKeys.all, "frequency", window] as const,
};

export function useSocioProfiles() {
  return useQuery({
    queryKey: contextKeys.profiles(),
    queryFn: () =>
      apiFetch<MunicipalitySocioProfile[]>("/sociodemographic/profiles"),
  });
}

export interface FreqSummary {
  operator: string;
  stop_id: string;
  stop_name: string | null;
  departures: number;
  departures_per_hour: number;
}

export function useFrequencyData(timeWindow: string) {
  return useQuery({
    queryKey: contextKeys.frequency(timeWindow),
    queryFn: async (): Promise<FreqSummary[]> => {
      const geo = await apiFetch<{
        features: Array<{ properties: FreqSummary }>;
      }>(`/sociodemographic/frequency/geojson?time_window=${timeWindow}&min_dph=0`);
      return geo.features.map((f) => f.properties);
    },
  });
}
