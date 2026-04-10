"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  DashboardSummary,
  ScoreDistributionBucket,
  PurposeBreakdown,
  ServiceCoverage,
  MunicipalitySocioProfile,
} from "@/lib/api";
import type { AreaRanking } from "@/components/dashboard-charts";

export interface DashboardData {
  summary: DashboardSummary;
  distribution: ScoreDistributionBucket[];
  purposes: PurposeBreakdown[];
  comarcas: AreaRanking[];
  municipalities: AreaRanking[];
  coverage: ServiceCoverage[];
  socioProfiles: MunicipalitySocioProfile[];
}

export const dashboardKeys = {
  all: ["dashboard"] as const,
  combined: (departureTime: string) =>
    [...dashboardKeys.all, "combined", departureTime] as const,
  areaDetail: (areaType: string, code: string) =>
    [...dashboardKeys.all, "area-detail", areaType, code] as const,
};

export function useDashboardData(departureTime = "08:00") {
  return useQuery({
    queryKey: dashboardKeys.combined(departureTime),
    queryFn: async (): Promise<DashboardData> => {
      const [summary, distribution, purposes, comarcas, municipalities, coverage, socioProfiles] =
        await Promise.all([
          apiFetch<DashboardSummary>(`/dashboard/summary?departure_time=${departureTime}`),
          apiFetch<ScoreDistributionBucket[]>(`/dashboard/score-distribution?departure_time=${departureTime}`),
          apiFetch<PurposeBreakdown[]>(`/dashboard/purpose-breakdown?departure_time=${departureTime}`),
          apiFetch<AreaRanking[]>(`/dashboard/comarca-ranking?departure_time=${departureTime}`),
          apiFetch<AreaRanking[]>(`/dashboard/municipality-ranking?departure_time=${departureTime}`),
          apiFetch<ServiceCoverage[]>(`/dashboard/service-coverage?departure_time=${departureTime}`),
          apiFetch<MunicipalitySocioProfile[]>("/sociodemographic/profiles").catch(
            () => [] as MunicipalitySocioProfile[],
          ),
        ]);
      return { summary, distribution, purposes, comarcas, municipalities, coverage, socioProfiles };
    },
  });
}
