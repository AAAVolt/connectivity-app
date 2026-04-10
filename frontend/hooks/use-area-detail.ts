"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { AreaDetail } from "@/lib/api";
import { dashboardKeys } from "./use-dashboard-data";

export function useAreaDetail(
  areaType: "comarca" | "municipality",
  code: string | null,
) {
  return useQuery({
    queryKey: dashboardKeys.areaDetail(areaType, code ?? ""),
    queryFn: () =>
      apiFetch<AreaDetail>(
        `/dashboard/${areaType}/${code}?departure_time=08:00`,
      ),
    enabled: !!code,
  });
}
