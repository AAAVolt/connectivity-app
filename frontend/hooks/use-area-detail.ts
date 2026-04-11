"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { AreaDetail } from "@/lib/api";
import { dashboardKeys, STALE_TIMES } from "@/lib/query-keys";

export function useAreaDetail(
  areaType: "comarca" | "municipality",
  code: string | null,
  departureTime = "08:00",
) {
  return useQuery({
    queryKey: dashboardKeys.areaDetail(areaType, code ?? ""),
    queryFn: () =>
      apiFetch<AreaDetail>(
        `/dashboard/${areaType}/${code}?departure_time=${departureTime}`,
      ),
    enabled: !!code,
    staleTime: STALE_TIMES.COMPUTED,
  });
}
