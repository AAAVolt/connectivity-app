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
import { dashboardKeys, STALE_TIMES } from "@/lib/query-keys";

export interface DashboardData {
  summary: DashboardSummary;
  distribution: ScoreDistributionBucket[];
  purposes: PurposeBreakdown[];
  comarcas: AreaRanking[];
  municipalities: AreaRanking[];
  coverage: ServiceCoverage[];
  socioProfiles: MunicipalitySocioProfile[];
}

export { dashboardKeys };

export function useDashboardData(departureTime = "08:00") {
  return useQuery({
    queryKey: dashboardKeys.combined(departureTime),
    staleTime: STALE_TIMES.COMPUTED,
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
